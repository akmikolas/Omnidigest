"""
Twitter Intelligence Domain — Processor.
Handles AI-driven triage, impact scoring, and business logic for Twitter data.
推特智能领域 — 处理器。
处理基于 AI 的过滤、影响打分以及推特数据的业务逻辑。

Uses the generic OnePass framework for unified AI analysis.
使用通用 OnePass 框架进行统一的 AI 分析。
"""
import logging
import asyncio
from typing import List, Dict, Optional
from ...core.database import DatabaseManager
from ...core.llm_manager import LLMManager
from ...config import settings
from ..core.onepass import OnePassProcessor, OnePassConfig
from .models import TwitterTriageResult, TwitterBatchTriageResult, OnePassTwitterResult, OnePassTwitterBatchResult
from .alerter import TwitterAlerter

logger = logging.getLogger(__name__)


class TwitterProcessor:
    """
    Orchestrator for Twitter intelligence and triage.
    推特智能和过滤的编排器。

    Uses the generic OnePass framework for unified AI analysis.
    使用通用 OnePass 框架进行统一的 AI 分析。
    """

    def __init__(self, db: DatabaseManager, llm_manager: LLMManager, alerter: TwitterAlerter = None):
        """
        Initializes the TwitterProcessor.
        初始化 TwitterProcessor。
        """
        self.db = db
        self.llm = llm_manager
        self.alerter = alerter or TwitterAlerter()

        # Initialize generic OnePass processor for Twitter
        self.onepass_config = OnePassConfig(
            name="twitter",
            prompt_template=settings.prompt_twitter_onepass,
            response_model=OnePassTwitterBatchResult,
            context_providers=["recent_events"],
            temperature=0.1,
            max_context_items=10
        )

        self.onepass = OnePassProcessor(
            config=self.onepass_config,
            llm_manager=llm_manager,
            db=db,
            rag_client=None  # Twitter doesn't use RAG currently
        )

    async def _handle_event_for_tweet(self, stream: Dict, result: TwitterTriageResult) -> Optional[Dict]:
        """
        Handles event clustering for a significant tweet.
        处理重要推文的事件聚类。

        Returns:
            Dict with event data if alert should be pushed, None otherwise.
        """
        if not settings.enable_twitter_alerts:
            return None

        lookback = settings.twitter_event_lookback_minutes
        threshold = settings.twitter_event_push_threshold

        # Search for similar events using the summary
        search_text = result.summary_zh or stream.get('raw_text', '')[:200]
        similar_events = await asyncio.to_thread(
            self.db.find_similar_twitter_events,
            search_text=search_text,
            lookback_minutes=lookback
        )

        if similar_events:
            # Link to existing event
            existing_event = similar_events[0]
            event_id = existing_event['id']
            await asyncio.to_thread(
                self.db.link_tweet_to_event,
                event_id=event_id,
                tweet_id=stream['tweet_id'],
                author=stream['author_screen_name']
            )
            new_count = await asyncio.to_thread(
                self.db.increment_twitter_event_source_count,
                event_id=event_id
            )

            # Update event with latest summary if needed
            await asyncio.to_thread(
                self.db.update_twitter_event,
                event_id=event_id,
                title=result.summary_zh[:512] if result.summary_zh else None,
                summary=result.summary_zh,
                score=result.impact_score
            )

            logger.info(f"📎 Linked tweet {stream['tweet_id']} to existing event {event_id} (source_count={new_count})")

            # Push alert if threshold reached
            if new_count >= threshold:
                # Get updated event with sources
                event = await asyncio.to_thread(self.db.get_twitter_event_by_id, event_id)
                sources = await asyncio.to_thread(self.db.get_twitter_event_tweet_sources, event_id)
                if event:
                    event['sources'] = sources
                    return event
        else:
            # Create new event
            event_id = await asyncio.to_thread(
                self.db.create_twitter_event,
                title=result.summary_zh[:512] if result.summary_zh else stream['raw_text'][:512],
                summary=result.summary_zh,
                category=result.category,
                score=result.impact_score,
                first_tweet_id=stream['tweet_id']
            )

            if event_id:
                await asyncio.to_thread(
                    self.db.link_tweet_to_event,
                    event_id=event_id,
                    tweet_id=stream['tweet_id'],
                    author=stream['author_screen_name']
                )
                logger.info(f"🆕 Created new event {event_id} for tweet {stream['tweet_id']}")

                # Don't push alert immediately for new event - wait for more sources
                # Only push when source_count reaches threshold
                if 1 >= threshold:
                    event = await asyncio.to_thread(self.db.get_twitter_event_by_id, event_id)
                    sources = await asyncio.to_thread(self.db.get_twitter_event_tweet_sources, event_id)
                    if event:
                        event['sources'] = sources
                        return event
                return None

        return None

    async def _triage_batch(self, tweets: List[Dict]) -> List[TwitterTriageResult]:
        """
        Analyzes and scores a batch of tweets using a single LLM call.
        获取一批推文并使用单次 LLM 调用进行分析和打分。
        """
        # Format context for batch prompt
        context_parts = []
        for tweet in tweets:
            part = f"--- TWEET_ID: {tweet['tweet_id']} ---\n"
            part += f"Author: @{tweet['author_screen_name']}\n"
            part += f"Content: {tweet['raw_text']}\n"
            part += f"Is_Reply: {tweet['is_reply']}\n"
            context_parts.append(part)
            
        prompt = settings.prompt_twitter_batch_triage.format(context="\n".join(context_parts))
        
        try:
            batch_result: TwitterBatchTriageResult = await self.llm.chat_completion_structured(
                response_model=TwitterBatchTriageResult,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                service_name="twitter_batch_triage_processor"
            )
            return batch_result.results
        except Exception as e:
            logger.error(f"Batch triage failed for {len(tweets)} tweets: {e}")
            return []

    async def _triage_batch_onepass(self, tweets: List[Dict]) -> List[OnePassTwitterResult]:
        """
        One-Pass analysis: analyzes and scores a batch of tweets with event matching in a single LLM call.
        One-Pass 分析：在单次 LLM 调用中分析、打分并匹配事件。

        Uses the generic OnePass framework.
        使用通用 OnePass 框架。
        """
        # Format tweets context as input_data
        tweets_text = ""
        for tweet in tweets:
            tweets_text += f"--- TWEET_ID: {tweet['tweet_id']} ---\n"
            tweets_text += f"Author: @{tweet['author_screen_name']}\n"
            tweets_text += f"Content: {tweet['raw_text']}\n"
            tweets_text += f"Is_Reply: {tweet['is_reply']}\n\n"

        try:
            # Use generic OnePass processor
            batch_result = await self.onepass.process(
                input_data=tweets_text,
                context_params={
                    "event_type": "twitter",
                    "hours": 24,
                    "limit": 10
                }
            )

            if batch_result and hasattr(batch_result, 'results'):
                return batch_result.results
            return []
            return batch_result.results
        except Exception as e:
            logger.error(f"One-Pass batch triage failed for {len(tweets)} tweets: {e}")
            return []

    async def _handle_event_for_onepass_result(
        self,
        stream: Dict,
        result: OnePassTwitterResult
    ) -> Optional[Dict]:
        """
        Handles event linking for One-Pass result.
        处理 One-Pass 结果的事件链接。

        Uses LLM's matched_event_id when available, falls back to DB search if not.
        当 LLM 提供 matched_event_id 时使用它，否则回退到数据库搜索。
        """
        if not settings.enable_twitter_alerts:
            return None

        threshold = settings.twitter_event_push_threshold

        # Use LLM's matched_event_id if available
        if result.matched_event_id:
            event_id = result.matched_event_id
            # Link to existing event
            await asyncio.to_thread(
                self.db.link_tweet_to_event,
                event_id=event_id,
                tweet_id=stream['tweet_id'],
                author=stream['author_screen_name']
            )
            new_count = await asyncio.to_thread(
                self.db.increment_twitter_event_source_count,
                event_id=event_id
            )
            # Update event
            await asyncio.to_thread(
                self.db.update_twitter_event,
                event_id=event_id,
                title=result.summary_zh[:512] if result.summary_zh else None,
                summary=result.summary_zh,
                score=result.impact_score
            )
            logger.info(f"📎 [OnePass] Linked tweet {stream['tweet_id']} to event {event_id} (source_count={new_count})")

            # Push alert if threshold reached
            if new_count >= threshold:
                event = await asyncio.to_thread(self.db.get_twitter_event_by_id, event_id)
                sources = await asyncio.to_thread(self.db.get_twitter_event_tweet_sources, event_id)
                tweet_urls = await asyncio.to_thread(self.db.get_twitter_event_tweet_urls, event_id)
                if event:
                    event['sources'] = sources
                    event['tweet_urls'] = tweet_urls
                    return event
            return None

        # Fallback: LLM says should create new event or no match
        if result.should_create_event and result.is_significant:
            event_id = await asyncio.to_thread(
                self.db.create_twitter_event,
                title=result.summary_zh[:512] if result.summary_zh else stream['raw_text'][:512],
                summary=result.summary_zh,
                category=result.category,
                score=result.impact_score,
                first_tweet_id=stream['tweet_id']
            )

            if event_id:
                await asyncio.to_thread(
                    self.db.link_tweet_to_event,
                    event_id=event_id,
                    tweet_id=stream['tweet_id'],
                    author=stream['author_screen_name']
                )
                logger.info(f"🆕 [OnePass] Created new event {event_id} for tweet {stream['tweet_id']}")

                # Push alert if threshold is 1
                if 1 >= threshold:
                    event = await asyncio.to_thread(self.db.get_twitter_event_by_id, event_id)
                    sources = await asyncio.to_thread(self.db.get_twitter_event_tweet_sources, event_id)
                    if event:
                        event['sources'] = sources
                        return event
                return None

        # Fallback: DB search if LLM didn't provide event matching
        if result.is_significant and result.impact_score >= settings.twitter_impact_threshold:
            search_text = result.summary_zh or stream.get('raw_text', '')[:200]
            similar_events = await asyncio.to_thread(
                self.db.find_similar_twitter_events,
                search_text=search_text,
                lookback_minutes=settings.twitter_event_lookback_minutes
            )
            if similar_events:
                # Use DB matched event
                return await self._handle_event_for_tweet(stream, TwitterTriageResult(
                    tweet_id=result.tweet_id,
                    is_significant=result.is_significant,
                    impact_score=result.impact_score,
                    summary_zh=result.summary_zh,
                    category=result.category,
                    is_thread_start=result.is_thread_start
                ))

        return None

    async def process_pending_tweets(self, limit: int = 50):
        """
        Triage and score all pending (status=0) tweets in batches using One-Pass.
        使用 One-Pass 模式批量过滤并打分所有待处理（status=0）的推文。

        Now uses single LLM call for triage + scoring + event matching.
        现在使用单次 LLM 调用完成分类 + 打分 + 事件匹配。
        """
        streams = await asyncio.to_thread(self.db.get_unprocessed_twitter_streams, limit=limit)
        if not streams:
            logger.info("No pending tweets to process.")
            return

        # Define batch size
        batch_size = 10
        logger.info(f"Processing One-Pass triage for {len(streams)} tweets in {len(range(0, len(streams), batch_size))} batches (batch_size={batch_size})...")

        processed_count = 0
        for i in range(0, len(streams), batch_size):
            batch = streams[i:i + batch_size]
            logger.info(f"-> Batch {i//batch_size + 1}: Sending {len(batch)} tweets to LLM (One-Pass)...")
            # Use One-Pass method: triage + scoring + event matching in single call
            results = await self._triage_batch_onepass(batch)
            logger.info(f"<- Batch {i//batch_size + 1}: Received {len(results)} results from LLM.")

            # Create a lookup for results by tweet_id
            result_map = {res.tweet_id: res for res in results}

            for stream in batch:
                result = result_map.get(stream['tweet_id'])
                if result:
                    processed_count += 1
                    status = 1 if result.is_significant else 2  # 1: Important, 2: Noise
                    await asyncio.to_thread(
                        self.db.update_twitter_stream_triage,
                        stream_id=stream['id'],
                        status=status,
                        impact_score=result.impact_score,
                        category=result.category,
                        summary=result.summary_zh,
                        is_thread_start=result.is_thread_start
                    )

                    if settings.enable_twitter_alerts and result.is_significant and result.impact_score >= settings.twitter_impact_threshold:
                        # Handle event clustering using One-Pass result
                        event_to_alert = await self._handle_event_for_onepass_result(stream, result)
                        if event_to_alert:
                            # Mark event as pushed
                            await asyncio.to_thread(
                                self.db.mark_twitter_event_pushed,
                                event_id=event_to_alert['id']
                            )
                            # Push event-level alert
                            logger.info(f"🔥 Event Alert: {event_to_alert['event_title']} (Sources: {event_to_alert['source_count']})")
                            self.alerter.push_alert(event_to_alert)
                        else:
                            logger.info(f"⏳ Queued for aggregation (@{stream['author_screen_name']}): {result.summary_zh}")
                    elif result.is_significant:
                        logger.info(f"📌 Interesting (@{stream['author_screen_name']}): {result.summary_zh} (Score: {result.impact_score})")
                    else:
                        logger.debug(f"💤 Noise from @{stream['author_screen_name']}")
                else:
                    logger.warning(f"No result returned for tweet_id {stream['tweet_id']} in batch.")
                    # Fallback or mark as error
                    await asyncio.to_thread(self.db.update_twitter_stream_triage, stream['id'], 3, 0, None, None, False)

        logger.info(f"Finished Twitter One-Pass triage cycle. Successfully updated {processed_count} tweets.")
