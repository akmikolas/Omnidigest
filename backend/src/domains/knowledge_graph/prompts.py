"""
Knowledge Graph Extraction Prompts.
知识图谱抽取提示词模板。

Defines the LLM prompts used to extract entities and relationships from news articles.
定义用于从新闻文章中抽取实体和关系的 LLM 提示词。
"""

# Relation type normalization mapping (Chinese -> English normalized)
RELATION_NORMALIZATION = {
    # Leadership roles
    "ceo": "CEO_OF",
    "首席执行官": "CEO_OF",
    "总裁": "PRESIDENT_OF",
    "董事长": "CHAIRMAN_OF",
    "总经理": "GENERAL_MANAGER_OF",
    "创始人": "FOUNDER_OF",
    "创立": "FOUNDED",
    "成立于": "FOUNDED_IN",
    "创建": "FOUNDED",

    # Business relations
    "收购": "ACQUIRED",
    "并购": "ACQUIRED",
    "收购了": "ACQUIRED",
    "投资": "INVESTS_IN",
    "参股": "INVESTS_IN",
    "合作": "COOPERATES_WITH",
    " partnership": "COOPERATES_WITH",
    "联合": "COOPERATES_WITH",
    "竞争": "COMPETES_WITH",
    "对抗": "COMPETES_WITH",

    # Location relations
    "位于": "LOCATED_IN",
    "总部在": "HEADQUARTERED_IN",
    "在...成立": "FOUNDED_IN",
    "访问": "VISITED",
    "访问了": "VISITED",

    # Political relations
    "制裁": "SANCTIONED",
    "制裁了": "SANCTIONED",
    "支持": "SUPPORTS",
    "反对": "OPPOSES",
    "发言": "SPEAKS_AT",
    "签署": "SIGNED",
    "访问": "VISITED",

    # Family relations
    "父亲": "FATHER_OF",
    "母亲": "MOTHER_OF",
    "儿子": "SON_OF",
    "女儿": "DAUGHTER_OF",
    "配偶": "SPOUSE_OF",
    "结婚": "MARRIED_TO",

    # Event relations
    "参加": "PARTICIPATED_IN",
    "出席": "ATTENDED",
    "主持": "HOSTED",
}

KG_EXTRACTION_PROMPT = """你是一个专业的知识图谱构建助手。请从以下新闻全文中抽取所有关键实体和它们之间的关系。

## 规则
1. 实体类型只能是以下之一：Person（人物）、Organization（组织机构）、Location（地点）
2. 人名统一使用最常见的中文译名（如 "Donald Trump" → "特朗普"）
3. 只抽取文中明确提到的事实，不要推测或编造
4. 关系 (relation) 必须使用归一化的关系类型代码（见下方列表），不要使用原始的中文动词
5. 重点关注政治人物的立场和言论，若文中提到某人对另一人的评价或任命，必须在 relations 中体现。
6. 如果文中没有明确的实体或关系，返回空数组

## 归一化关系类型列表
CEO_OF: 担任首席执行官/总裁
PRESIDENT_OF: 担任总裁/董事长
FOUNDER_OF: 创始人/创办人
FOUNDED/FOUNDED_IN: 创立/成立
ACQUIRED: 收购/并购
INVESTS_IN: 投资/参股
COOPERATES_WITH: 合作/联合
COMPETES_WITH: 竞争/对抗
LOCATED_IN: 位于
HEADQUARTERED_IN: 总部在
VISITED: 访问/访问了
SANCTIONED: 制裁
SUPPORTS: 支持
OPPOSES: 反对
SPEAKS_AT: 发言/演讲
SIGNED: 签署
PARTICIPATED_IN: 参加/参与
ATTENDED: 出席
HOSTED: 主持

## 输出格式
严格按以下 JSON 格式返回，不要包含任何其他文字：
{{
  "entities": [
    {{"name": "实体名称", "type": "Person|Organization|Location", "description": "一句话描述该实体在本文中的角色"}}
  ],
  "relations": [
    {{"source": "源实体名称", "relation": "归一化关系类型", "target": "目标实体名称", "context": "原文中支持该关系的关键句子"}}
  ]
}}

## 新闻全文
事件标题：{event_title}
分类：{category}
全文内容：
{raw_text}
"""

ENTITY_RESOLUTION_PROMPT = """你是一个实体消歧专家。以下是从新闻中抽取的一批"{entity_type}"类型的实体名称。
其中可能存在重复——同一个实体因中英文、别名、简称等原因被记录为不同的名称。

请找出所有指代同一实体的名称组，并为每组选择一个最规范的中文名称作为标准名（canonical_name）。

## 规则
1. 只合并你**确定**是同一实体的名称，不确定的不要合并
2. 标准名优先使用中文全名（如"特朗普"优于"Trump"）
3. 如果所有名称都是英文且没有公认中文译名，保留最完整的英文名
4. 不要合并仅仅名字相似但实际是不同人/组织/地点的实体

## 实体列表
{entity_list}

## 输出格式
严格按以下 JSON 格式返回，只返回需要合并的组，不需要合并的实体不要出现在输出中：
{{
  "merge_groups": [
    {{
      "canonical_name": "标准名称",
      "aliases": ["别名1", "别名2"],
      "reason": "合并理由"
    }}
  ]
}}
如果没有需要合并的实体，返回 {{"merge_groups": []}}
"""
