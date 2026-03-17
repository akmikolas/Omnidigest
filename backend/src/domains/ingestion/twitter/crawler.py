"""
Twitter Ingestion Domain — Crawler.
Handles the scraping loop and high-water mark logic for raw tweet ingestion.
推特摄取领域 — 爬虫。
处理原始推文摄取的抓取循环和高水位线逻辑。
"""
import logging
import time
import random
from typing import List, Dict
from ....core.database import DatabaseManager
from ....config import settings
from .client import TwitterClient

logger = logging.getLogger(__name__)

class TwitterCrawler:
    """
    Orchestrator for Twitter raw ingestion.
    推特原始摄取的编排器。
    """
    
    def __init__(self, db: DatabaseManager, client: TwitterClient):
        """
        Initializes the TwitterCrawler.
        初始化 TwitterCrawler。
        """
        self.db = db
        self.client = client

    def run_ingestion_loop(self):
        """
        Main loop for ingesting tweets from monitored users.
        从被监听用户摄取推文的主循环。
        """
        logger.info("Starting Twitter ingestion loop...")
        
        users = self.db.get_monitored_twitter_users()
        if not users:
            logger.info("No active monitored Twitter users found.")
            return

        for user in users:
            self._process_user(user)
            # Add delay between users to avoid rate limiting
            delay = settings.twitter_request_delay_seconds
            time.sleep(random.uniform(delay * 0.5, delay * 1.5))

        logger.info("Twitter ingestion loop completed.")

    def _process_user(self, user: Dict):
        """
        Processes a single monitored user's timeline.
        处理单个被监听用户的时效线。
        """
        rest_id = user['rest_id']
        screen_name = user['screen_name']
        since_id = user['last_seen_tweet_id'] or '0'
        
        logger.info(f"Processing Twitter user: @{screen_name} (since_id={since_id})")
        
        tweets = self.client.fetch_user_tweets(rest_id)
        if not tweets:
            logger.info(f"No tweets fetched for @{screen_name} (rest_id={rest_id}).")
            return
        
        logger.info(f"Fetched {len(tweets)} tweets for @{screen_name}.")

        # Sort tweets by ID to find the newest one for HWM
        tweets.sort(key=lambda x: int(x['id']))
        
        new_tweets_count = 0
        latest_tweet_id = since_id
        
        for tweet in tweets:
            # Skip if already seen
            if int(tweet['id']) <= int(since_id):
                continue
            
            # Persist to raw twitter stream
            res = self.db.add_twitter_stream_raw(
                tweet_id=tweet['id'],
                author=tweet.get('screen_name'),
                text=tweet.get('text'),
                is_reply=tweet.get('is_reply', False),
                reply_to=tweet.get('reply_to'),
                metadata=tweet.get('raw')
            )
            
            if res:
                new_tweets_count += 1
                if int(tweet['id']) > int(latest_tweet_id):
                    latest_tweet_id = tweet['id']

        if new_tweets_count > 0:
            logger.info(f"✅ Ingested {new_tweets_count} new tweets from @{screen_name}.")
            self.db.update_twitter_high_water_mark(rest_id, latest_tweet_id)
        else:
            logger.info(f"No new tweets found for @{screen_name}.")
