"""
Dgraph Client — Connection management, schema initialization, and mutation helpers for the Knowledge Graph.
Dgraph 客户端 — 用于知识图谱的连接管理、Schema 初始化和 Mutation 写入辅助。

Uses pydgraph (gRPC) to interact with Dgraph Alpha.
使用 pydgraph (gRPC) 与 Dgraph Alpha 交互。
"""
import logging
import json
import math
from datetime import datetime
import pydgraph
from ...config import settings

logger = logging.getLogger(__name__)

# Dgraph Schema (DQL format)
# Dgraph Schema（DQL 格式）
DGRAPH_SCHEMA = """
    # Node types
    type Person {
        name
        description
        mentioned_in
    }

    type Organization {
        name
        description
        mentioned_in
    }

    type Location {
        name
        description
        mentioned_in
    }

    type Event {
        title
        summary
        category
        event_date
        source_event_id
        involves_person
        involves_org
        located_at
        related_to
    }

    # Predicates
    name: string @index(exact, term) .
    description: string .
    title: string @index(fulltext) .
    summary: string .
    category: string @index(exact) .
    event_date: datetime @index(hour) .
    source_event_id: string @index(exact) .
    mentioned_in: [uid] @reverse .
    involves_person: [uid] @reverse .
    involves_org: [uid] @reverse .
    located_at: [uid] @reverse .
    related_to: [uid] @reverse .

    # Entity extensions (v2)
    sources: [string] .
    confidence: float .
    aliases: [string] @index(term) .
    relation_type: string @index(exact) .

    # Time-aware relations
    start_time: datetime .
    end_time: datetime .
    extracted_at: datetime .

    # Relation metadata
    relation_source: string .
"""


class DgraphClient:
    """
    Wrapper around pydgraph for Knowledge Graph operations.
    对 pydgraph 的封装，用于知识图谱操作。
    """

    def __init__(self):
        """
        Initializes a gRPC connection to Dgraph Alpha.
        初始化到 Dgraph Alpha 的 gRPC 连接。
        """
        self.stub = pydgraph.DgraphClientStub(settings.dgraph_alpha_url)
        self.client = pydgraph.DgraphClient(self.stub)
        logger.info(f"Dgraph client initialized: {settings.dgraph_alpha_url}")

    def init_schema(self):
        """
        Applies the Knowledge Graph schema to Dgraph. Safe to run multiple times (idempotent).
        将知识图谱 Schema 应用到 Dgraph。可以安全地多次运行（幂等）。
        """
        op = pydgraph.Operation(schema=DGRAPH_SCHEMA)
        self.client.alter(op)
        logger.info("✅ Dgraph schema initialized successfully.")

    def upsert_entity(self, txn, name: str, entity_type: str, description: str = "") -> str:
        """
        Upserts an entity node (Person, Organization, or Location).
        Returns the UID of the node (existing or newly created).
        插入或更新一个实体节点（Person、Organization 或 Location）。
        返回节点的 UID（已存在的或新创建的）。
        """
        # Query for existing node by name + type
        query = f"""
        {{
            entity(func: eq(name, "{name}")) @filter(type({entity_type})) {{
                uid
            }}
        }}
        """
        res = txn.query(query)
        data = json.loads(res.json)

        if data.get("entity") and len(data["entity"]) > 0:
            return data["entity"][0]["uid"]

        # Create new
        nquad = f"""
            _:entity <name> "{name}" .
            _:entity <description> "{description}" .
            _:entity <dgraph.type> "{entity_type}" .
        """
        mutation = txn.create_mutation(set_nquads=nquad)
        request = txn.create_request(mutations=[mutation], commit_now=False)
        response = txn.do_request(request)
        uid = response.uids.get("entity", "")
        return uid

    def upsert_event(self, txn, event_id: str, title: str, summary: str, category: str, event_date: str = None) -> str:
        """
        Upserts an Event node linked to the PostgreSQL event ID.
        插入或更新一个 Event 节点，关联到 PostgreSQL 的 event ID。
        """
        query = f"""
        {{
            event(func: eq(source_event_id, "{event_id}")) @filter(type(Event)) {{
                uid
            }}
        }}
        """
        res = txn.query(query)
        data = json.loads(res.json)

        if data.get("event") and len(data["event"]) > 0:
            return data["event"][0]["uid"]

        nquad = f"""
            _:event <title> "{self._escape(title)}" .
            _:event <summary> "{self._escape(summary)}" .
            _:event <category> "{category}" .
            _:event <source_event_id> "{event_id}" .
            _:event <dgraph.type> "Event" .
        """
        if event_date:
            nquad += f'    _:event <event_date> "{event_date}" .\n'

        mutation = txn.create_mutation(set_nquads=nquad)
        request = txn.create_request(mutations=[mutation], commit_now=False)
        response = txn.do_request(request)
        return response.uids.get("event", "")

    def link_entity_to_event(self, txn, event_uid: str, entity_uid: str, entity_type: str):
        """
        Creates a directional relationship from an Event to an Entity node.
        创建从 Event 到 Entity 节点的定向关系。
        """
        predicate_map = {
            "Person": "involves_person",
            "Organization": "involves_org",
            "Location": "located_at"
        }
        predicate = predicate_map.get(entity_type, "involves_person")
        nquad = f"""
            <{event_uid}> <{predicate}> <{entity_uid}> .
            <{entity_uid}> <mentioned_in> <{event_uid}> .
        """
        mutation = txn.create_mutation(set_nquads=nquad)
        return mutation

    def create_relation(self, txn, source_uid: str, target_uid: str, relation: str):
        """
        Creates a labeled edge between two entities using facets.
        使用 facets 在两个实体间创建带标签的边。
        """
        nquad = f'<{source_uid}> <related_to> <{target_uid}> (relation="{self._escape(relation)}") .\n'
        mutation = txn.create_mutation(set_nquads=nquad)
        return mutation

    def new_txn(self):
        """Returns a new Dgraph transaction. / 返回一个新的 Dgraph 事务。"""
        return self.client.txn()

    def get_stats(self) -> dict:
        """
        Returns basic statistics about the Knowledge Graph.
        返回知识图谱的基本统计信息。
        """
        query = """
        {
            persons(func: type(Person)) { count(uid) }
            orgs(func: type(Organization)) { count(uid) }
            locations(func: type(Location)) { count(uid) }
            events(func: type(Event)) { count(uid) }
        }
        """
        txn = self.client.txn(read_only=True)
        try:
            res = txn.query(query)
            data = json.loads(res.json)
            logger.info(f"Dgraph stats query result: {data}")

            # Get relation counts using simpler queries
            total_relations = 0
            relation_counts = []

            # Query each relation type separately
            for pred in ["involves_person", "involves_org", "located_at", "related_to", "mentioned_in"]:
                pred_query = f"""
                {{
                    result(func: has({pred})) {{ count(uid) }}
                }}
                """
                pred_res = txn.query(pred_query)
                pred_data = json.loads(pred_res.json)
                count = pred_data.get("result", [{}])[0].get("count", 0) if pred_data.get("result") else 0
                total_relations += count
                if count > 0:
                    relation_counts.append({"type": pred.replace("_", " ").title(), "count": count})

            return {
                "persons": data.get("persons", [{}])[0].get("count", 0),
                "organizations": data.get("orgs", [{}])[0].get("count", 0),
                "locations": data.get("locations", [{}])[0].get("count", 0),
                "events": data.get("events", [{}])[0].get("count", 0),
                "total_relations": total_relations,
                "top_relations": relation_counts
            }
        finally:
            txn.discard()

    def get_recent_entities(self, limit: int = 10) -> list:
        """
        Returns recent entities from the Knowledge Graph.
        返回知识图谱中最近的实体。
        """
        query = """
        {
            recent(func: type(Person), first: 10) { uid name }
            recent_orgs(func: type(Organization), first: 10) { uid name }
            recent_locs(func: type(Location), first: 10) { uid name }
            recent_events(func: type(Event), first: 10) { uid title }
        }
        """
        txn = self.client.txn(read_only=True)
        try:
            res = txn.query(query)
            data = json.loads(res.json)

            entities = []
            # Add persons
            for item in data.get("recent", []):
                entities.append({"uid": item.get("uid"), "name": item.get("name", ""), "type": "Person", "relation_count": 0})
            # Add organizations
            for item in data.get("recent_orgs", []):
                entities.append({"uid": item.get("uid"), "name": item.get("name", ""), "type": "Organization", "relation_count": 0})
            # Add locations
            for item in data.get("recent_locs", []):
                entities.append({"uid": item.get("uid"), "name": item.get("name", ""), "type": "Location", "relation_count": 0})
            # Add events
            for item in data.get("recent_events", []):
                entities.append({"uid": item.get("uid"), "name": item.get("title", ""), "type": "Event", "relation_count": 0})

            return entities[:limit]
        finally:
            txn.discard()

    def get_all_entities(self, entity_type: str) -> list:
        """
        Fetches all entities of a given type with their UIDs.
        获取指定类型的所有实体及其 UID。
        """
        query = f"""
        {{
            entities(func: type({entity_type}), first: 1000) {{
                uid
                name
            }}
        }}
        """
        txn = self.client.txn(read_only=True)
        try:
            res = txn.query(query)
            data = json.loads(res.json)
            return data.get("entities", [])
        finally:
            txn.discard()

    def get_graph_visualization(self, limit: int = 15) -> dict:
        """
        Returns nodes and connections for graph visualization.
        返回用于图谱可视化的节点和连接。
        """
        # Get entities with their connections
        query = """
        {
            persons(func: type(Person), first: 5) {
                uid
                name
                mentioned_in {
                    uid
                    title
                }
            }
            orgs(func: type(Organization), first: 5) {
                uid
                name
                mentioned_in {
                    uid
                    title
                }
            }
            locations(func: type(Location), first: 5) {
                uid
                name
                mentioned_in {
                    uid
                    title
                }
            }
            events(func: type(Event), first: 5) {
                uid
                title
                involves_person {
                    uid
                    name
                }
                involves_org {
                    uid
                    name
                }
                located_at {
                    uid
                    name
                }
            }
        }
        """
        txn = self.client.txn(read_only=True)
        try:
            res = txn.query(query)
            data = json.loads(res.json)

            nodes = []
            connections = []
            node_map = {}
            colors = {
                "Person": "#4ade80",
                "Organization": "#60a5fa",
                "Location": "#f472b6",
                "Event": "#fbbf24"
            }

            # Process persons
            for item in data.get("persons", []):
                uid = item.get("uid")
                name = item.get("name", "Unknown")
                if uid and name:
                    nodes.append({"id": uid, "label": name[:20], "color": colors["Person"]})
                    node_map[uid] = len(nodes) - 1

            # Process organizations
            for item in data.get("orgs", []):
                uid = item.get("uid")
                name = item.get("name", "Unknown")
                if uid and name:
                    nodes.append({"id": uid, "label": name[:20], "color": colors["Organization"]})
                    node_map[uid] = len(nodes) - 1

            # Process locations
            for item in data.get("locations", []):
                uid = item.get("uid")
                name = item.get("name", "Unknown")
                if uid and name:
                    nodes.append({"id": uid, "label": name[:20], "color": colors["Location"]})
                    node_map[uid] = len(nodes) - 1

            # Process events and their connections
            for item in data.get("events", []):
                uid = item.get("uid")
                title = item.get("title", "Unknown Event")[:20]
                if uid:
                    nodes.append({"id": uid, "label": title, "color": colors["Event"]})
                    node_map[uid] = len(nodes) - 1

                    # Add connections from event to persons
                    for person in item.get("involves_person", []):
                        person_uid = person.get("uid")
                        if person_uid and person_uid in node_map:
                            connections.append({
                                "x1": 0, "y1": 0,  # Will be calculated below
                                "x2": 0, "y2": 0
                            })
                            # Store for later resolution
                            connections[-1]["from"] = uid
                            connections[-1]["to"] = person_uid

                    # Add connections from event to organizations
                    for org in item.get("involves_org", []):
                        org_uid = org.get("uid")
                        if org_uid and org_uid in node_map:
                            connections.append({
                                "from": uid,
                                "to": org_uid,
                                "x1": 0, "y1": 0, "x2": 0, "y2": 0
                            })

                    # Add connections from event to locations
                    for loc in item.get("located_at", []):
                        loc_uid = loc.get("uid")
                        if loc_uid and loc_uid in node_map:
                            connections.append({
                                "from": uid,
                                "to": loc_uid,
                                "x1": 0, "y1": 0, "x2": 0, "y2": 0
                            })

            # Limit nodes
            nodes = nodes[:limit]

            # Calculate positions in a circular layout
            width, height = 800, 400
            center_x, center_y = width // 2, height // 2
            radius = min(width, height) // 3

            for i, node in enumerate(nodes):
                if i == 0:
                    node["x"] = center_x
                    node["y"] = center_y
                else:
                    angle = (2 * 3.14159 * i) / len(nodes)
                    node["x"] = center_x + radius * (1 if i % 2 == 0 else -1) * abs(math.cos(angle))
                    node["y"] = center_y + radius * (1 if i % 3 == 0 else -1) * math.sin(angle)

            # Resolve connection coordinates
            final_connections = []
            for conn in connections:
                from_idx = node_map.get(conn.get("from"))
                to_idx = node_map.get(conn.get("to"))
                if from_idx is not None and to_idx is not None and from_idx < len(nodes) and to_idx < len(nodes):
                    final_connections.append({
                        "x1": nodes[from_idx]["x"],
                        "y1": nodes[from_idx]["y"],
                        "x2": nodes[to_idx]["x"],
                        "y2": nodes[to_idx]["y"]
                    })

            return {
                "nodes": nodes,
                "connections": final_connections[:20]  # Limit connections
            }
        finally:
            txn.discard()

    def merge_entities(self, canonical_uid: str, canonical_name: str, alias_uids: list, entity_type: str):
        """
        Merges alias entities into the canonical entity.
        Rewires all edges pointing to/from aliases to the canonical node, then deletes aliases.
        将别名实体合并到标准实体。将所有指向别名的边重定向到标准节点，然后删除别名。
        """
        predicate_map = {
            "Person": "involves_person",
            "Organization": "involves_org",
            "Location": "located_at"
        }
        predicate = predicate_map.get(entity_type, "involves_person")

        txn = self.client.txn()
        try:
            # For each alias, find all events that reference it and rewire to canonical
            for alias_uid in alias_uids:
                # Query events linked to alias via reverse edge
                query = f"""
                {{
                    events(func: uid({alias_uid})) {{
                        ~{predicate} {{
                            uid
                        }}
                    }}
                }}
                """
                res = txn.query(query)
                data = json.loads(res.json)

                events = data.get("events", [])
                if events and events[0].get(f"~{predicate}"):
                    for event in events[0][f"~{predicate}"]:
                        event_uid = event["uid"]
                        # Add edge from event to canonical
                        set_nquad = f'<{event_uid}> <{predicate}> <{canonical_uid}> .\n'
                        # Remove edge from event to alias
                        del_nquad = f'<{event_uid}> <{predicate}> <{alias_uid}> .\n'
                        mutation = txn.create_mutation(set_nquads=set_nquad, del_nquads=del_nquad)
                        request = txn.create_request(mutations=[mutation], commit_now=False)
                        txn.do_request(request)

                # Also handle related_to edges
                query_rel = f"""
                {{
                    rels(func: uid({alias_uid})) {{
                        related_to {{ uid }}
                        ~related_to {{ uid }}
                    }}
                }}
                """
                res_rel = txn.query(query_rel)
                data_rel = json.loads(res_rel.json)

                if data_rel.get("rels") and data_rel["rels"]:
                    rel_node = data_rel["rels"][0]
                    # Outgoing related_to
                    for target in rel_node.get("related_to", []):
                        set_nquad = f'<{canonical_uid}> <related_to> <{target["uid"]}> .\n'
                        del_nquad = f'<{alias_uid}> <related_to> <{target["uid"]}> .\n'
                        mutation = txn.create_mutation(set_nquads=set_nquad, del_nquads=del_nquad)
                        request = txn.create_request(mutations=[mutation], commit_now=False)
                        txn.do_request(request)
                    # Incoming related_to
                    for source in rel_node.get("~related_to", []):
                        set_nquad = f'<{source["uid"]}> <related_to> <{canonical_uid}> .\n'
                        del_nquad = f'<{source["uid"]}> <related_to> <{alias_uid}> .\n'
                        mutation = txn.create_mutation(set_nquads=set_nquad, del_nquads=del_nquad)
                        request = txn.create_request(mutations=[mutation], commit_now=False)
                        txn.do_request(request)

                # Delete the alias node
                del_nquad = f'<{alias_uid}> * * .\n'
                mutation = txn.create_mutation(del_nquads=del_nquad)
                request = txn.create_request(mutations=[mutation], commit_now=False)
                txn.do_request(request)

            # Update the canonical node's name to the standard name
            set_nquad = f'<{canonical_uid}> <name> "{self._escape(canonical_name)}" .\n'
            mutation = txn.create_mutation(set_nquads=set_nquad)
            request = txn.create_request(mutations=[mutation], commit_now=False)
            txn.do_request(request)

            txn.commit()
            logger.info(f"  ✅ Merged {len(alias_uids)} alias(es) into '{canonical_name}'")
        except Exception as e:
            logger.error(f"  ❌ Merge failed for '{canonical_name}': {e}")
        finally:
            txn.discard()

    def search_entities(self, name: str = None, entity_type: str = None,
                        start_time: str = None, end_time: str = None,
                        limit: int = 50) -> list:
        """
        Search entities with optional filters.
        根据可选过滤器搜索实体。
        """
        # Build query based on filters
        filters = []
        if entity_type:
            filters.append(f"type({entity_type})")
        if name:
            filters.append(f"anyofterms(name, \"{name}\")")

        filter_str = " AND ".join(filters) if filters else "type(Person)"
        if not entity_type and not name:
            filter_str = "type(Person)"

        query = f"""
        {{
            entities(func: {filter_str}, first: {limit}) {{
                uid
                name
                dgraph.type
                description
                aliases
                confidence
                sources
                extracted_at
            }}
        }}
        """

        # For Organization and Location, we need separate queries
        all_entities = []
        types_to_query = [entity_type] if entity_type else ["Person", "Organization", "Location"]

        for etype in types_to_query:
            if entity_type and etype != entity_type:
                continue

            if etype == "Person":
                q = f'{{ entities(func: eq(name, "{name}"), first: {limit}) {{ uid name dgraph.type description aliases confidence sources extracted_at }} }}' if name else f'{{ entities(func: type(Person), first: {limit}) {{ uid name dgraph.type description aliases confidence sources extracted_at }} }}'
            elif etype == "Organization":
                q = f'{{ entities(func: eq(name, "{name}"), first: {limit}) {{ uid name dgraph.type description aliases confidence sources extracted_at }} }}' if name else f'{{ entities(func: type(Organization), first: {limit}) {{ uid name dgraph.type description aliases confidence sources extracted_at }} }}'
            else:
                q = f'{{ entities(func: eq(name, "{name}"), first: {limit}) {{ uid name dgraph.type description aliases confidence sources extracted_at }} }}' if name else f'{{ entities(func: type(Location), first: {limit}) {{ uid name dgraph.type description aliases confidence sources extracted_at }} }}'

            if name:
                q = f'''
                {{
                    entities(func: anyofterms(name, "{name}"), first: {limit}) {{
                        uid
                        name
                        dgraph.type
                        description
                        aliases
                        confidence
                        sources
                        extracted_at
                    }}
                }}
                '''

            txn = self.client.txn(read_only=True)
            try:
                res = txn.query(q)
                data = json.loads(res.json)
                for e in data.get("entities", []):
                    all_entities.append(e)
            finally:
                txn.discard()

        return all_entities[:limit]

    def get_entity_details(self, uid: str) -> dict:
        """
        Get detailed information about a specific entity.
        获取特定实体的详细信息。
        """
        query = f"""
        {{
            entity(func: uid({uid})) {{
                uid
                name
                dgraph.type
                description
                aliases
                confidence
                sources
                extracted_at

                # Event relations
                mentioned_in {{
                    uid
                    title
                    category
                    event_date
                    source_event_id
                }}

                # Entity relations
                related_to @facets {{
                    uid
                    name
                    dgraph.type
                }}

                ~related_to @facets {{
                    uid
                    name
                    dgraph.type
                }}
            }}
        }}
        """
        txn = self.client.txn(read_only=True)
        try:
            res = txn.query(query)
            data = json.loads(res.json)
            entities = data.get("entity", [])
            if entities:
                return entities[0]
            return {}
        finally:
            txn.discard()

    def get_relations(self, from_uid: str = None, to_uid: str = None,
                      relation_type: str = None, limit: int = 100) -> list:
        """
        Get relations with optional filters.
        获取带有可选过滤器的关系。
        """
        # Query all entities and their outgoing relations
        # Using separate queries for each entity type
        all_relations = []
        entity_types = ["Person", "Organization", "Location"]

        txn = self.client.txn(read_only=True)
        try:
            for entity_type in entity_types:
                query = f"""
                {{
                    entities(func: type({entity_type}), first: {limit}) {{
                        uid
                        name
                        dgraph.type
                        related_to {{
                            uid
                            name
                            dgraph.type
                        }}
                    }}
                }}
                """
                res = txn.query(query)
                data = json.loads(res.json)

                for item in data.get("entities", []):
                    for target in item.get("related_to", []):
                        # Apply filters
                        if from_uid and item.get("uid") != from_uid:
                            continue
                        if to_uid and target.get("uid") != to_uid:
                            continue

                        all_relations.append({
                            "source_uid": item.get("uid"),
                            "source_name": item.get("name", ""),
                            "source_type": entity_type,
                            "target_uid": target.get("uid"),
                            "target_name": target.get("name", ""),
                            "target_type": target.get("dgraph.type", ""),
                            "relation": "related_to"
                        })

            # Also query for reverse relations (~related_to)
            for entity_type in entity_types:
                query = f"""
                {{
                    entities(func: type({entity_type}), first: {limit}) {{
                        uid
                        name
                        dgraph.type
                        ~related_to {{
                            uid
                            name
                            dgraph.type
                        }}
                    }}
                }}
                """
                res = txn.query(query)
                data = json.loads(res.json)

                for item in data.get("entities", []):
                    for source in item.get("~related_to", []):
                        # Apply filters
                        if from_uid and source.get("uid") != from_uid:
                            continue
                        if to_uid and item.get("uid") != to_uid:
                            continue

                        all_relations.append({
                            "source_uid": source.get("uid"),
                            "source_name": source.get("name", ""),
                            "source_type": source.get("dgraph.type", ""),
                            "target_uid": item.get("uid"),
                            "target_name": item.get("name", ""),
                            "target_type": entity_type,
                            "relation": "related_to"
                        })

            return all_relations[:limit]
        finally:
            txn.discard()

    def search_path(self, start_name: str, end_name: str, max_depth: int = 3) -> list:
        """
        Find shortest path between two entities.
        查找两个实体之间的最短路径。
        """
        # First, find UIDs for start and end entities
        start_query = f'{{ start(func: eq(name, "{start_name}")) {{ uid name }} }}'
        end_query = f'{{ end(func: eq(name, "{end_name}")) {{ uid name }} }}'

        txn = self.client.txn(read_only=True)
        try:
            # Get start entity
            res = txn.query(start_query)
            data = json.loads(res.json)
            start_entities = data.get("start", [])
            if not start_entities:
                return []
            start_uid = start_entities[0]["uid"]

            # Get end entity
            res = txn.query(end_query)
            data = json.loads(res.json)
            end_entities = data.get("end", [])
            if not end_entities:
                return []
            end_uid = end_entities[0]["uid"]

            # Simple BFS for path finding (limited depth)
            # Query for connections
            path_query = f"""
            {{
                paths as var(func: uid({start_uid})) {{
                    related_to {{
                        uid
                        name
                    }}
                }}
            }}
            """

            # Get all related entities
            query = f"""
            {{
                start(func: uid({start_uid})) {{
                    uid
                    name
                    related_to {{
                        uid
                        name
                        related_to @filter(uid({end_uid})) {{
                            uid
                            name
                        }}
                    }}
                }}
            }}
            """
            res = txn.query(query)
            data = json.loads(res.json)

            paths = []
            start_node = data.get("start", [])
            if start_node:
                for rel in start_node[0].get("related_to", []):
                    if rel.get("uid") == end_uid:
                        paths.append([
                            {"uid": start_uid, "name": start_name},
                            {"uid": rel.get("uid"), "name": rel.get("name", "")}
                        ])
                    else:
                        # Check second level
                        for second_rel in rel.get("related_to", []):
                            if second_rel.get("uid") == end_uid:
                                paths.append([
                                    {"uid": start_uid, "name": start_name},
                                    {"uid": rel.get("uid"), "name": rel.get("name", "")},
                                    {"uid": second_rel.get("uid"), "name": second_rel.get("name", "")}
                                ])

            return paths[:5]  # Return up to 5 paths
        finally:
            txn.discard()

    def upsert_entity_with_sources(self, txn, name: str, entity_type: str,
                                    description: str = "", source_event_id: str = None,
                                    confidence: float = 1.0) -> str:
        """
        Upserts an entity with source tracking.
        带来源追踪的插入或更新实体。
        """
        # Query for existing node by name + type
        query = f"""
        {{
            entity(func: eq(name, "{name}")) @filter(type({entity_type})) {{
                uid
                sources
            }}
        }}
        """
        res = txn.query(query)
        data = json.loads(res.json)

        if data.get("entity") and len(data["entity"]) > 0:
            existing_uid = data["entity"][0]["uid"]
            existing_sources = data["entity"][0].get("sources", [])

            # Add new source if not exists
            if source_event_id and source_event_id not in existing_sources:
                existing_sources.append(source_event_id)
                set_nquad = f'<{existing_uid}> <sources> "{source_event_id}" .\n'
                mutation = txn.create_mutation(set_nquads=set_nquad)
                request = txn.create_request(mutations=[mutation], commit_now=False)
                txn.do_request(request)

            return existing_uid

        # Create new entity with sources
        nquad = f"""
            _:entity <name> "{self._escape(name)}" .
            _:entity <description> "{self._escape(description)}" .
            _:entity <dgraph.type> "{entity_type}" .
            _:entity <confidence> "{confidence}" .
            _:entity <extracted_at> "{self._escape(datetime.now().isoformat())}" .
        """
        if source_event_id:
            nquad += f'    _:entity <sources> "{source_event_id}" .\n'

        mutation = txn.create_mutation(set_nquads=nquad)
        request = txn.create_request(mutations=[mutation], commit_now=False)
        response = txn.do_request(request)
        uid = response.uids.get("entity", "")
        return uid

    def get_top_countries_with_entities(self, top_n: int = 5) -> dict:
        """
        查询新闻最多的N个国家及其关联的实体和事件。
        Returns the top N countries by event count with linked persons and events.

        Args:
            top_n: 返回的国家数量，默认 5

        Returns:
            {"nodes": [...], "links": [...]}
        """
        txn = self.client.txn(read_only=True)
        try:
            # 第一步：查询所有国家
            all_countries_query = """
            {
                locations(func: type(Location)) {
                    uid
                    name
                }
            }
            """

            res = txn.query(all_countries_query)
            data = json.loads(res.json)
            locations = data.get("locations", [])

            # 第二步：对每个国家查询其事件数量
            location_counts = []
            for loc in locations:
                uid = loc.get("uid")
                name = loc.get("name", "Unknown")
                if not uid:
                    continue
                # 查询该国家的事件数量
                count_query = """
                {
                    check(func: uid(%s)) {
                        cnt: count(~located_at)
                    }
                }
                """ % uid
                count_res = txn.query(count_query)
                count_data = json.loads(count_res.json)
                count = count_data.get("check", [{}])[0].get("cnt", 0)
                location_counts.append({"uid": uid, "name": name, "count": count})

            # 在 Python 中按事件数量排序并取前 N 个
            sorted_locations = sorted(location_counts, key=lambda x: x.get("count", 0), reverse=True)[:top_n]

            nodes = []
            links = []
            seen_node_ids = set()

            for location in sorted_locations:
                country_uid = location.get("uid")
                country_name = location.get("name", "Unknown")
                news_count = location.get("count", 0)

                if not country_uid:
                    continue

                # 添加国家节点
                country_id = f"country_{country_uid}"
                nodes.append({
                    "id": country_id,
                    "type": "country",
                    "name": country_name,
                    "news_count": news_count,
                })
                seen_node_ids.add(country_id)

                # 第三步：查询该国家关联的事件和人物（限制每个国家最多5个事件）
                detail_query = """
                {
                    country(func: uid(%s)) {
                        ~located_at(orderdesc: event_date, first: 5) {
                            uid
                            title
                            involves_person(orderdesc: confidence, first: 3) {
                                uid
                                name
                            }
                        }
                    }
                }
                """ % country_uid

                detail_res = txn.query(detail_query)
                detail_data = json.loads(detail_res.json)
                country_detail = detail_data.get("country", [])

                if not country_detail:
                    continue

                for event in country_detail[0].get("~located_at", []):
                    event_uid = event.get("uid")
                    event_title = event.get("title", "Unknown Event")
                    if not event_uid:
                        continue

                    event_id = f"event_{event_uid}"
                    if event_id not in seen_node_ids:
                        nodes.append({
                            "id": event_id,
                            "type": "event",
                            "name": event_title,
                        })
                        seen_node_ids.add(event_id)

                    # 国家 -> 事件 链接
                    links.append({
                        "source": country_id,
                        "target": event_id,
                        "type": "located_at",
                    })

                    # 事件 -> 关联人物 链接
                    for person in event.get("involves_person", []):
                        person_uid = person.get("uid")
                        person_name = person.get("name", "Unknown")
                        if not person_uid:
                            continue

                        person_id = f"person_{person_uid}"
                        if person_id not in seen_node_ids:
                            nodes.append({
                                "id": person_id,
                                "type": "person",
                                "name": person_name,
                            })
                            seen_node_ids.add(person_id)

                        links.append({
                            "source": person_id,
                            "target": event_id,
                            "type": "involves",
                        })

            return {"nodes": nodes, "links": links}
        finally:
            txn.discard()

    def close(self):
        """Closes the gRPC connection. / 关闭 gRPC 连接。"""
        self.stub.close()

    @staticmethod
    def _escape(text: str) -> str:
        """Escapes special characters for N-Quad format. / 转义 N-Quad 格式的特殊字符。"""
        return text.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\r', '')
