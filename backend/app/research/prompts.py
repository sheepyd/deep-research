CLARIFY_PROMPT = """
You are the Supervisor agent for a deep research system.
Generate 3 to 5 short clarification questions that help scope a deep research task.
Return each question on its own line, no numbering.

User topic: {query}
Preferred response language: {language}
""".strip()

BUILD_BRIEF_PROMPT = """
You are the Supervisor agent preparing a research brief.
Combine the original topic with the user's answers into a concise brief that can guide a professional research workflow.
Output in {language}.

Topic:
{query}

User answers:
{answers}

Previous report plan:
{previous_plan}

Previous final report:
{previous_report}

Follow-up research request:
{follow_up_request}
""".strip()

REPORT_PLAN_PROMPT = """
You are the Supervisor agent planning a deep research project.
Write a concise research plan in Markdown with objectives, key angles, evidence requirements, and expected output structure.
Output in {language}.

Research brief:
{brief}
""".strip()

SEARCH_QUERY_PROMPT = """
You are the Supervisor agent generating web search tasks for a deep research workflow.
Return valid JSON only. The JSON must be an array of objects with keys "query" and "research_goal".
Create 3 to 5 focused search tasks.
Output language for the query text and goals should be {language}.

Research plan:
{plan}
""".strip()

SEARCH_SUMMARY_PROMPT = """
You are the Researcher agent summarizing search results for one research task.
Use the provided sources to produce:
1. A concise learning paragraph.
2. A short reasoning note that explains what mattered in these results.
Return valid JSON only with keys "learning" and "reasoning".
Output in {language}.

Search query: {query}
Research goal: {research_goal}

Sources:
{sources}
""".strip()

FINAL_REPORT_PROMPT = """
You are the Supervisor agent writing the final deep research report from researcher learnings.
Use the research plan and the collected learnings to produce a structured Markdown report with:
- Title
- Executive summary
- Key findings
- Analysis
- Risks and open questions
- References

Output in {language}.

Research plan:
{plan}

Collected learnings:
{learnings}
""".strip()
