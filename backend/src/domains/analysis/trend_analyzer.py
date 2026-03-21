"""
Trend analysis service. Uses LLMs to filter news articles and generate comprehensive trend reports based on database records.
趋势分析服务。使用 LLM 过滤新闻文章，并基于数据库记录生成综合趋势报告。
"""
import logging
import json
from ...core.database import DatabaseManager
from ..knowledge_base.rag_client import RAGClient
from ...config import settings

logger = logging.getLogger(__name__)

class AnalysisService:
    """
    Service for analyzing news trends using a two-stage LLM approach.
    使用两阶段 LLM 方法分析新闻趋势的服务。
    """
    def __init__(self, db: DatabaseManager, llm_manager):
        """
        Initializes the AnalysisService with required dependencies.
        使用所需的依赖项初始化 AnalysisService。
        
        Args:
            db (DatabaseManager): The database manager instance. / 数据库管理器实例。
            llm_manager (LLMManager): The LLM management service for dynamic model selection. / LLM 管理服务，用于动态模型选择。
        """
        self.db = db
        self.llm = llm_manager

    async def analyze_trends(self, query: str, days: int = 30) -> str:
        """
        Generates a comprehensive trend analysis report based on a user query. Uses a two-stage LLM process: 1. Filters recent database articles for relevance to the query. 2. Synthesizes the relevant articles into a formatted HTML report.
        基于用户查询生成全面的趋势分析报告。使用两阶段 LLM 流程：1. 过滤最近的数据库文章，找出与查询相关的文章。2. 将相关文章综合成格式化的 HTML 报告。
        
        Args:
            query (str): The research topic or question to analyze. / 要分析的搜索主题或问题。
            days (int, optional): The time window to look back in days. Defaults to 30. / 要回顾的时间窗口（以天为单位）。默认为 30。
            
        Returns:
            str: A formatted HTML string containing the analysis report, or an error message. / 包含分析报告的格式化 HTML 字符串，或错误消息。
        """
        if not self.llm:
            return "Error: LLM client not initialized."

        # Stage 1: Filter
        # 第一阶段：筛选
        articles = self.db.get_articles_by_date_range(days=days)
        if not articles:
            return f"No articles found in the last {days} days."

        logger.info(f"Analysis Stage 1: Filtering {len(articles)} articles for query '{query}'...")
        
        # Construct metadata list for LLM
        # 为 LLM 构建元数据列表
        meta_list = []
        for art in articles:
            meta_list.append({
                "id": str(art['id']),
                "title": art['title'],
                "summary": (art.get('summary_raw') or '')[:200], # Ensure string before slicing
                "score": art.get('score', 0)
            })
            
        system_prompt_s1 = "You are a research assistant. Filter the provided news articles to find those relevant to the user's research query."
        user_prompt_s1 = f"""
        Query: "{query}"
        
        Evaluate the following articles and select ONLY the ones that are relevant to answering the query.
        Return a JSON object with a single key "relevant_ids" containing a list of article IDs.
        
        Articles:
        {json.dumps(meta_list, ensure_ascii=False)}
        """
        
        try:
            content_s1 = await self.llm.chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt_s1},
                    {"role": "user", "content": user_prompt_s1}
                ],
                temperature=0.1,
                service_name="trend_analysis_stage1"
            )
            if not content_s1:
                return "Analysis failed: No output from LLM in stage 1."
                
            content_s1 = self.llm._clean_json_output(content_s1)
            data_s1 = json.loads(content_s1)
            relevant_ids = data_s1.get("relevant_ids", [])
            logger.info(f"Stage 1 Result: Found {len(relevant_ids)} relevant articles.")
            
        except Exception as e:
            logger.error(f"Stage 1 Error: {e}")
            return f"Analysis failed during filtering stage: {e}"

        if not relevant_ids:
            return "No relevant articles found matching your query."

        # Stage 2: Analyze
        # 第二阶段：分析
        logger.info("Analysis Stage 2: Fetching full content and generating report...")
        
        # Re-fetch full content for selected IDs (Optimization: could map from initial fetch if memory allows, but DB fetch is safer for large lists)
        # 重新获取所选 ID 的完整内容（优化：如果内存允许，可以从初始获取中映射，但对于大列表，DB 获取更安全）
        # Simulating fetch by filtering the initial list (since we only fetched metadata initially, we might need full content now)
        # Actually my get_articles_by_date_range didn't fetch full content. I need to fetch full content now.
        
        # Let's add a helper here or just loop fetch? Loop fetch is slow. 
        # Better: Filter logical list if I had content, but I don't.
        # I need a way to fetch multiple articles by ID.
        # Let's do a simple loop for now as relevant_ids shouldn't be huge (LLM context limit).
        
        full_context = ""
        for art_id in relevant_ids:
            # We need a get_article_by_id. DatabaseManager doesn't seem to have it exposed easily or I missed it.
            # I'll use a direct query here for expediency, or add to DB.
            # Let's add it to DB properly in next step if needed, or query directly here?
            # Actually, `get_article` is basic. Let's assume I should add `get_article` to DB or use `get_unclassified` pattern.
            # Wait, I can't easily modify DB from here without a tool call.
            # I will use a direct SQL execution via `self.db._get_connection()` which is accessible.
            try:
                with self.db._get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT title, content, source_url, publish_time FROM omnidigest.news_articles WHERE id = %s", (art_id,))
                        row = cur.fetchone()
                        if row:
                            title, content, url, pub_time = row
                            date_str = pub_time.strftime("%Y-%m-%d") if pub_time else "?"
                            full_context += f"Title: {title}\nDate: {date_str}\nSource: {url}\nContent:\n{content[:2000]}\n\n---\n\n" # Truncate huge articles
            except Exception as e:
                logger.error(f"Error fetching article {art_id}: {e}")

        # Final Prompt
        system_prompt_s2 = "You are a senior tech analyst. Write a comprehensive trend analysis report based on the provided news. You MUST format your output using ONLY Telegram-compatible HTML tags (<b>, <i>, <u>, <s>, <a href=\"...\">, <code>, <pre>). Do NOT use Markdown formatting (like **, *, #, -, `). Use standard Unicode bullet points (•) for lists instead of hyphens or asterisks."
        user_prompt_s2 = f"""
        Research Topic: "{query}"
        
        Based ONLY on the provided news articles below, write a detailed analysis.
        
        Structure:
        1. <b>Executive Summary</b>: Key takeaways (2-3 sentences).
        2. <b>Key Trends & Events</b>: Detailed breakdown of what happened.
        3. <b>Pattern Analysis</b>: Connect the dots between different events.
        4. <b>Implications</b>: What does this mean for the industry?
        
        Format Requirements:
        - Output ONLY valid HTML text.
        - Emphasize key terms with <b>.
        - Make lists using '• ' at the beginning of the line.
        - Reference specific articles by title/source where appropriate.
        
        News Context:
        {full_context}
        """

        try:
            content_s2 = await self.llm.chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt_s2},
                    {"role": "user", "content": user_prompt_s2}
                ],
                temperature=0.3,
                service_name="trend_analysis_stage2"
            )
            return content_s2 or "Analysis failed: No output from LLM in stage 2."
            
        except Exception as e:
            logger.error(f"Stage 2 Error: {e}")
            return f"Analysis failed during generation stage: {e}"
