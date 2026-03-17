"""
Knowledge Graph Extractor — Orchestrates the LLM-based triple extraction pipeline.
知识图谱抽取器 — 编排基于 LLM 的三元组抽取管线。

Reads unprocessed breaking news from PostgreSQL, uses LLM to extract entities
and relationships, and writes them into Dgraph.
从 PostgreSQL 中读取未处理的突发新闻，使用 LLM 抽取实体和关系，并写入 Dgraph。
"""
import json
import logging
import asyncio
from .dgraph_client import DgraphClient
from .prompts import KG_EXTRACTION_PROMPT, ENTITY_RESOLUTION_PROMPT
from ...config import settings
from ...core.database import DatabaseManager
from ...core.llm_manager import LLMManager

logger = logging.getLogger(__name__)


def _edit_distance(s1: str, s2: str) -> int:
    """Calculate edit distance between two strings."""
    if len(s1) < len(s2):
        return _edit_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)

    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


class KGExtractor:
    """
    Main orchestrator for the Knowledge Graph extraction pipeline.
    知识图谱抽取管线的主编排器。
    """

    def __init__(self, db: DatabaseManager, dgraph: DgraphClient, llm: LLMManager):
        """
        Initializes the KGExtractor with necessary clients.
        使用必要的客户端初始化 KGExtractor。
        
        Args:
            db (DatabaseManager): The primary relational database manager. / 主关系数据库管理器。
            dgraph (DgraphClient): The Dgraph graph database client. / Dgraph 图数据库客户端。
            llm (LLMManager): The LLM service for extraction. / 用于抽取的 LLM 服务。
        """
        self.db = db
        self.dgraph = dgraph
        self.llm = llm

    def get_unprocessed_streams(self, hours: int = 48) -> list:
        """
        Fetches breaking news streams that haven't been processed for KG extraction yet.
        获取尚未进行知识图谱抽取的突发新闻流。
        """
        query = """
            SELECT
                e.id AS event_id, e.event_title, e.summary, e.category,
                r.id AS stream_id, r.raw_text, r.source_platform, r.publish_time
            FROM breaking_events e
            JOIN event_stream_mapping m ON m.event_id = e.id
            JOIN breaking_stream_raw r ON r.id = m.stream_id
            WHERE r.kg_processed = FALSE
              AND r.created_at > NOW() - INTERVAL '1 hour' * %s
            ORDER BY r.created_at DESC
        """
        try:
            with self.db._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (hours,))
                    columns = [desc[0] for desc in cur.description]
                    return [dict(zip(columns, row)) for row in cur.fetchall()]
        except Exception as e:
            logger.error(f"Error fetching unprocessed streams: {e}")
            return []

    def mark_stream_processed(self, stream_id: str):
        """
        Marks a stream as processed for KG in PostgreSQL.
        在 PostgreSQL 中将流标记为已进行 KG 处理。
        """
        query = "UPDATE breaking_stream_raw SET kg_processed = TRUE WHERE id = %s"
        try:
            with self.db._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (stream_id,))
                conn.commit()
        except Exception as e:
            logger.error(f"Error marking stream {stream_id} as KG processed: {e}")

    async def extract_triples(self, event_title: str, category: str, raw_text: str) -> dict:
        """
        Calls LLM to extract entities and relationships from a news article.
        调用 LLM 从新闻文章中抽取实体 and 关系。

        Returns:
            dict with 'entities' and 'relations' lists, or None on failure.
        """
        prompt = KG_EXTRACTION_PROMPT.format(
            event_title=event_title,
            category=category,
            raw_text=raw_text[:4000]  # Truncate to avoid token overflow / 截断以避免 Token 溢出
        )

        try:
            content = await self.llm.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                service_name="kg_extract"
            )
            if not content:
                return None
                
            content = self.llm._clean_json_output(content)
            data = json.loads(content)
            entities = data.get("entities", [])
            relations = data.get("relations", [])
            logger.info(f"  Extracted {len(entities)} entities, {len(relations)} relations.")
            return data
        except Exception as e:
            logger.error(f"  LLM extraction failed: {e}")
            return None

    def write_to_dgraph(self, event_id: str, event_title: str, summary: str,
                         category: str, extraction: dict, event_date: str = None):
        """
        Writes extracted entities and relationships to Dgraph in a single transaction.
        在单个事务中将抽取的实体和关系写入 Dgraph。

        Args:
            event_id (str): The ID of the event record. / 事件记录的 ID。
            event_title (str): The title of the event. / 事件标题。
            summary (str): The event summary. / 事件摘要。
            category (str): The category of the event. / 事件类别。
            extraction (dict): The extracted JSON data. / 抽取的 JSON 数据。
            event_date (str, optional): The date of the event. / 事件日期（可选）。
        """
        txn = self.dgraph.new_txn()
        try:
            # 1. Upsert the Event node
            event_uid = self.dgraph.upsert_event(
                txn, str(event_id), event_title, summary, category, event_date
            )
            if not event_uid:
                logger.warning(f"  Failed to upsert Event node for {event_id}")
                return

            mutations = []
            entity_uid_map = {}

            # 2. Upsert entities with source tracking and link them to the event
            for entity in extraction.get("entities", []):
                name = entity.get("name", "").strip()
                etype = entity.get("type", "Person")
                desc = entity.get("description", "")
                if not name or etype not in ("Person", "Organization", "Location"):
                    continue

                # Use enhanced upsert with source tracking
                uid = self.dgraph.upsert_entity_with_sources(
                    txn, name, etype, desc, source_event_id=str(event_id)
                )
                if uid:
                    entity_uid_map[name] = uid
                    mu = self.dgraph.link_entity_to_event(txn, event_uid, uid, etype)
                    if mu: mutations.append(mu)

            # 3. Create inter-entity relations with normalized type
            for rel in extraction.get("relations", []):
                source_name = rel.get("source", "").strip()
                target_name = rel.get("target", "").strip()
                relation = rel.get("relation", "").strip()
                context = rel.get("context", "")  # Original context for reference
                if source_name in entity_uid_map and target_name in entity_uid_map and relation:
                    mu = self.dgraph.create_relation(
                        txn, entity_uid_map[source_name],
                        entity_uid_map[target_name], relation
                    )
                    if mu: mutations.append(mu)

            # 4. Execute collected edge mutations
            if mutations:
                request = txn.create_request(mutations=mutations, commit_now=False)
                txn.do_request(request)

            txn.commit()
            logger.info(f"  ✅ Written to Dgraph: Event [{event_id}]")

        except Exception as e:
            logger.error(f"  ❌ Dgraph write failed for Event [{event_id}]: {e}")
            import traceback; logger.error(traceback.format_exc())
        finally:
            txn.discard()

    async def run(self, hours: int = 48):
        """
        Main execution loop: fetch unprocessed streams, extract triples, write to Dgraph.
        主执行循环：获取未处理的流，抽取三元组，写入 Dgraph。
        """
        streams = self.get_unprocessed_streams(hours)
        if not streams:
            logger.info("No unprocessed streams found for KG extraction.")
            return

        logger.info(f"Found {len(streams)} unprocessed streams. Starting extraction...")

        # Group streams by event_id to avoid processing duplicate raw texts for the same event
        seen_events = set()
        for stream in streams:
            event_id = str(stream["event_id"])

            if event_id not in seen_events:
                seen_events.add(event_id)
                logger.info(f"Processing Event: '{stream['event_title']}' [{event_id}]")

                extraction = await self.extract_triples(
                    event_title=stream["event_title"],
                    category=stream.get("category", "Other"),
                    raw_text=stream["raw_text"]
                )

                if extraction:
                    self.write_to_dgraph(
                        event_id=event_id,
                        event_title=stream["event_title"],
                        summary=stream.get("summary", ""),
                        category=stream.get("category", "Other"),
                        extraction=extraction,
                        event_date=stream["publish_time"].isoformat() if stream.get("publish_time") else None
                    )

            # Mark stream as processed regardless (even if event was already handled by another stream)
            self.mark_stream_processed(str(stream["stream_id"]))

        logger.info(f"✅ KG Extraction complete. Processed {len(seen_events)} unique events from {len(streams)} streams.")

    async def resolve_entities(self):
        """
        Runs entity resolution across all entity types using LLM disambiguation.
        使用 LLM 消歧在所有实体类型上运行实体合并。
        """
        entity_types = ["Person", "Organization", "Location"]
        total_merged = 0

        for entity_type in entity_types:
            entities = self.dgraph.get_all_entities(entity_type)
            if len(entities) < 2:
                logger.info(f"[{entity_type}] Only {len(entities)} entities, skipping resolution.")
                continue

            names = [e["name"] for e in entities]
            uid_map = {e["name"]: e["uid"] for e in entities}

            logger.info(f"[{entity_type}] Resolving {len(names)} entities...")

            # Send to LLM for duplicate detection
            entity_list = "\n".join(f"- {name}" for name in sorted(names))
            prompt = ENTITY_RESOLUTION_PROMPT.format(
                entity_type=entity_type,
                entity_list=entity_list
            )

            try:
                content = await self.llm.chat_completion(
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.0,
                    service_name="kg_resolve"
                )
                if not content:
                    continue
                
                content = self.llm._clean_json_output(content)
                data = json.loads(content)
                merge_groups = data.get("merge_groups", [])

                if not merge_groups:
                    logger.info(f"[{entity_type}] No duplicates found.")
                    continue

                logger.info(f"[{entity_type}] Found {len(merge_groups)} merge group(s):")
                for group in merge_groups:
                    canonical = group["canonical_name"]
                    aliases = group["aliases"]
                    reason = group.get("reason", "")
                    logger.info(f"  → '{canonical}' ← {aliases}  ({reason})")

                    # Find UIDs for canonical and aliases
                    # Canonical might be a new name (translated), so find it or use first alias
                    canonical_uid = uid_map.get(canonical)
                    alias_uids = []

                    if not canonical_uid:
                        # Canonical name might be a translation not in the graph yet
                        # Use the first alias as the canonical node and rename it
                        for alias in aliases:
                            if alias in uid_map:
                                canonical_uid = uid_map[alias]
                                break

                    if not canonical_uid:
                        logger.warning(f"  ⚠ Could not find UID for canonical '{canonical}', skipping.")
                        continue

                    for alias in aliases:
                        if alias in uid_map and uid_map[alias] != canonical_uid:
                            alias_uids.append(uid_map[alias])

                    if alias_uids:
                        self.dgraph.merge_entities(canonical_uid, canonical, alias_uids, entity_type)
                        total_merged += len(alias_uids)

            except Exception as e:
                logger.error(f"[{entity_type}] Resolution failed: {e}")

        logger.info(f"✅ Entity Resolution complete. Merged {total_merged} duplicate(s) total.")

    def _is_similar(self, name1: str, name2: str) -> bool:
        """
        Check if two entity names are similar (type-aware + similarity).
        检查两个实体名称是否相似（类型感知 + 相似度）。

        Returns True if:
        - Exact match (case insensitive)
        - One is substring of the other
        - Edit distance <= 2
        """
        if not name1 or not name2:
            return False

        n1, n2 = name1.lower().strip(), name2.lower().strip()

        # 1. Exact match
        if n1 == n2:
            return True

        # 2. Substring check (one contains the other)
        if n1 in n2 or n2 in n1:
            return True

        # 3. Edit distance check (threshold: 2)
        if _edit_distance(n1, n2) <= 2:
            return True

        return False

    def _group_similar_entities(self, entities: list, entity_type: str) -> list:
        """
        Pre-group entities by similarity before LLM resolution.
        在 LLM 消解前按相似度预分组实体。
        """
        if len(entities) < 2:
            return []

        # Build groups based on similarity
        groups = []
        processed = set()

        for i, entity1 in enumerate(entities):
            if entity1["uid"] in processed:
                continue

            # Start a new group with this entity
            group = [entity1]
            processed.add(entity1["uid"])

            # Find similar entities
            for j, entity2 in enumerate(entities):
                if i == j or entity2["uid"] in processed:
                    continue

                if self._is_similar(entity1["name"], entity2["name"]):
                    group.append(entity2)
                    processed.add(entity2["uid"])

            # Only return groups with more than 1 entity
            if len(group) > 1:
                groups.append(group)

        logger.info(f"[{entity_type}] Pre-grouped into {len(groups)} similar groups")
        return groups
