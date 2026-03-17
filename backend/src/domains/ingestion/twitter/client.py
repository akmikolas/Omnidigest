"""
Twitter Ingestion Domain — Scraping Client.
Handles the low-level interaction with Twitter using account pools and browser-like headers.
推特摄取领域 — 爬虫客户端。
使用账号池和类浏览器请求头处理与推特的低级交互。
"""
import logging
import requests
import json
import random
from typing import List, Dict, Optional
from ....core.database import DatabaseManager
from ....config import settings

logger = logging.getLogger(__name__)

class TwitterClient:
    """
    Client for scraping Twitter data using a pool of accounts.
    使用账号池抓取推特数据的客户端。
    """
    
    _BROWSER_HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'max-age=0',
    }

    def __init__(self, db: DatabaseManager):
        """
        Initializes the TwitterClient with a database manager.
        使用数据库管理器初始化 TwitterClient。
        """
        self.db = db
        self.current_account = None

    def _select_account(self) -> bool:
        """
        Selects a random active account from the pool.
        从池中随机选择一个活跃账号。
        """
        accounts = self.db.get_active_twitter_accounts()
        if not accounts:
            logger.error("No active Twitter accounts available in the pool.")
            return False

        # Randomly select an account to distribute load
        import random
        self.current_account = random.choice(accounts)
        logger.info(f"Using Twitter account: {self.current_account['username']}")
        return True

    def _get_headers(self) -> Dict:
        """
        Generates headers with authentication tokens for the current account.
        为当前账号生成带有认证令牌的请求头。
        """
        if not self.current_account:
            return self._BROWSER_HEADERS
        
        headers = self._BROWSER_HEADERS.copy()
        headers.update({
            'Authorization': 'Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA', # Global Twitter Bearer
            'x-twitter-auth-type': 'OAuth2Session',
            'x-twitter-active-user': 'yes',
            'x-twitter-client-language': 'en',
            'x-csrf-token': self.current_account['ct0'],
            'Cookie': f"auth_token={self.current_account['auth_token']}; ct0={self.current_account['ct0']};"
        })
        return headers

    def fetch_user_tweets(self, rest_id: str, count: int = 20, _retry_count: int = 0) -> List[Dict]:
        """
        Fetches the latest tweets for a given user ID using GraphQL.
        使用 GraphQL 获取给定用户 ID 的最新推文。

        Args:
            rest_id: Twitter user ID
            count: Number of tweets to fetch
            _retry_count: Internal counter to prevent infinite recursion (max 3 retries)
        """
        max_retries = 3
        if _retry_count >= max_retries:
            logger.warning(f"Max retries ({max_retries}) reached for user {rest_id}. Giving up.")
            return []

        if not self.current_account and not self._select_account():
            return []

        # Twitter GraphQL UserTweets endpoint (v1.7.0 update)
        # 2026-03-11: Reverting to twitter.com base URL as api.x.com gave 404
        query_id = "5M8UuGym7_VyIEggQIyjxQ"
        url = f"https://twitter.com/i/api/graphql/{query_id}/UserTweets"
        
        variables = {
            "userId": str(rest_id),
            "count": count,
            "includePromotedContent": True,
            "withQuickPromoteEligibilityTweetFields": True,
            "withVoice": True
        }
        
        features = {
            "rweb_video_screen_enabled": False,
            "profile_label_improvements_pcf_label_in_post_enabled": True,
            "responsive_web_profile_redirect_enabled": False,
            "rweb_tipjar_consumption_enabled": False,
            "verified_phone_label_enabled": False,
            "creator_subscriptions_tweet_preview_api_enabled": True,
            "responsive_web_graphql_timeline_navigation_enabled": True,
            "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
            "premium_content_api_read_enabled": False,
            "communities_web_enable_tweet_community_results_fetch": True,
            "c9s_tweet_anatomy_moderator_badge_enabled": True,
            "responsive_web_grok_analyze_button_fetch_trends_enabled": False,
            "responsive_web_grok_analyze_post_followups_enabled": False,
            "responsive_web_jetfuel_frame": True,
            "responsive_web_grok_share_attachment_enabled": True,
            "responsive_web_grok_annotations_enabled": True,
            "articles_preview_enabled": True,
            "responsive_web_edit_tweet_api_enabled": True,
            "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
            "view_counts_everywhere_api_enabled": True,
            "longform_notetweets_consumption_enabled": True,
            "responsive_web_twitter_article_tweet_consumption_enabled": True,
            "tweet_awards_web_tipping_enabled": False,
            "content_disclosure_indicator_enabled": True,
            "content_disclosure_ai_generated_indicator_enabled": True,
            "responsive_web_grok_show_grok_translated_post": False,
            "responsive_web_grok_analysis_button_from_backend": True,
            "post_ctas_fetch_enabled": True,
            "freedom_of_speech_not_reach_fetch_enabled": True,
            "standardized_nudges_misinfo": True,
            "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
            "longform_notetweets_rich_text_read_enabled": True,
            "longform_notetweets_inline_media_enabled": False,
            "responsive_web_grok_image_annotation_enabled": True,
            "responsive_web_grok_imagine_annotation_enabled": True,
            "responsive_web_grok_community_note_auto_translation_is_enabled": False,
            "responsive_web_enhance_cards_enabled": False
        }

        field_toggles = {"withArticlePlainText": False}

        params = {
            "variables": json.dumps(variables),
            "features": json.dumps(features),
            "fieldToggles": json.dumps(field_toggles)
        }

        try:
            # Note: In a real production environment, we should use a proxy here
            response = requests.get(url, headers=self._get_headers(), params=params, timeout=30)
            
            if response.status_code == 429:
                logger.warning(f"Rate limit hit for account {self.current_account['username']}. Cooling down.")
                self.db.update_twitter_account_status(
                    self.current_account['id'],
                    'cooling',
                    "Rate limit hit",
                    cooling_minutes=settings.twitter_account_cooling_minutes
                )
                self.current_account = None
                return self.fetch_user_tweets(rest_id, count, _retry_count + 1) # Retry with next account
            
            response.raise_for_status()
            data = response.json()
            
            # Robustly find 'instructions' in the JSON response
            instructions = []
            
            def find_instructions(obj):
                """
                Recursively search for 'instructions' key in nested JSON structure.
                递归搜索嵌套 JSON 结构中的 'instructions' 键。
                """
                if isinstance(obj, dict):
                    if 'instructions' in obj:
                        return obj['instructions']
                    for v in obj.values():
                        res = find_instructions(v)
                        if res: return res
                elif isinstance(obj, list):
                    for item in obj:
                        res = find_instructions(item)
                        if res: return res
                return None

            instructions = find_instructions(data)
            if not instructions:
                logger.warning(f"Could not find 'instructions' in GraphQL response. Keys: {list(data.get('data', {}).get('user', {}).keys())}")
                # Save for inspection
                with open("/tmp/twitter_failed_response.json", "w") as f:
                    json.dump(data, f)

                # Check if response indicates rate limiting or account restriction
                # Empty user data could mean many things, NOT necessarily rate limiting:
                # - The user account may be suspended or protected
                # - The user may not exist
                # - Twitter may have returned a different error format
                # Only put in cooling if we've actually hit rate limit (HTTP 429 above)
                user_data = data.get('data', {}).get('user', {})
                if not user_data or user_data == {}:
                    # Empty user data is NOT necessarily rate limiting
                    # Just return empty results and continue - don't penalize the account
                    logger.warning(f"Empty user data for {rest_id}. This could mean: user suspended/protected, or user has no recent tweets. Not putting account in cooling.")
                    return []

                return []
            
            logger.info(f"Found {len(instructions)} instructions in GraphQL response.")

            tweets = []
            for instr in instructions:
                type_ = instr.get('type')
                if type_ != 'TimelineAddEntries':
                    continue
                
                entries = instr.get('entries', [])
                logger.info(f"Processing TimelineAddEntries with {len(entries)} entries.")
                
                for entry in entries:
                    content = entry.get('content', {})
                    if content.get('entryType') != 'TimelineTimelineItem':
                        continue
                    
                    tweet_results = content.get('itemContent', {}).get('tweet_results', {})
                    tweet_result = tweet_results.get('result', {})
                    
                    if not tweet_result:
                        continue
                        
                    # Handle Retweets vs Regular Tweets
                    legacy = tweet_result.get('legacy')
                    if not legacy and 'tweet' in tweet_result:
                        # Sometimes it's wrapped in 'tweet' for blocked/filtered results
                        tweet_result = tweet_result.get('tweet', {}).get('result', {})
                        legacy = tweet_result.get('legacy')
                    
                    if not legacy:
                        continue
                        
                    tweet_id = legacy.get('id_str')
                    full_text = legacy.get('full_text')
                    
                    # Extract author (screen_name)
                    core_data = tweet_result.get('core', {})
                    user_results = core_data.get('user_results', {})
                    user_res = user_results.get('result', {})
                    
                    # Try 'core' first (new GraphQL style), then fallback to 'legacy'
                    screen_name = user_res.get('core', {}).get('screen_name')
                    if not screen_name:
                        screen_name = user_res.get('legacy', {}).get('screen_name')
                    
                    if tweet_id and full_text:
                        tweets.append({
                            'id': tweet_id,
                            'text': full_text,
                            'screen_name': screen_name,
                            'is_reply': legacy.get('in_reply_to_status_id_str') is not None,
                            'reply_to': legacy.get('in_reply_to_status_id_str'),
                            'raw': tweet_result
                        })
            
            # Update account status on success
            self.db.update_twitter_account_status(self.current_account['id'], 'active')
            return tweets

        except Exception as e:
            logger.error(f"Error fetching tweets for {rest_id}: {e}")
            if self.current_account:
                # Log error and potentially increment fail count
                self.db.update_twitter_account_status(self.current_account['id'], 'error', str(e))
            return []

    def _parse_tweets(self, data: Dict) -> List[Dict]:
        """
        Parses the complex Twitter GraphQL response into a simple list of tweet objects.
        将复杂的 Twitter GraphQL 响应解析为简单的推文对象列表。
        """
        tweets = []
        try:
            instructions = data.get('data', {}).get('user', {}).get('result', {}).get('timeline_v2', {}).get('timeline', {}).get('instructions', [])
            for instr in instructions:
                if instr.get('type') == 'TimelineAddEntries':
                    for entry in instr.get('entries', []):
                        content = entry.get('content', {})
                        if content.get('entryType') == 'TimelineTimelineItem':
                            tweet_data = content.get('itemContent', {}).get('tweet_results', {}).get('result', {})
                            if not tweet_data: continue
                            
                            # Handle Retweets
                            if tweet_data.get('__typename') == 'TweetWithVisibilityResults':
                                tweet_data = tweet_data.get('tweet', {})
                            
                            legacy = tweet_data.get('legacy', {})
                            if legacy:
                                tweets.append({
                                    'id': legacy.get('id_str'),
                                    'full_text': legacy.get('full_text'),
                                    'created_at': legacy.get('created_at'),
                                    'author': tweet_data.get('core', {}).get('user_results', {}).get('result', {}).get('legacy', {}).get('screen_name'),
                                    'is_reply': legacy.get('in_reply_to_status_id_str') is not None,
                                    'reply_to': legacy.get('in_reply_to_status_id_str'),
                                    'metadata': legacy
                                })
        except Exception as e:
            logger.error(f"Error parsing Twitter GraphQL response: {e}")
        
        return tweets
