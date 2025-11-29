# יכולת עיבוד מקבילי משולבת - מדריך שימוש
## Parallel Processing Capability - Integrated into Agent

---

## מה בנינו?

יצרנו **subagent מיוחד** שמטפל ברשימות במקביל ומשולב בסוכן הראשי!

### הארכיטקטורה:

```
User → Grok Agent (chat) → calls "task" tool → Parallel Processor SubAgent
                                                    ↓
                                        [Send API - Map-Reduce]
                                                    ↓
                                     N Workers in Parallel
                                                    ↓
                                        Aggregated Results
                                                    ↓
                                    Back to Grok Agent
                                                    ↓
                                          User sees results
```

### המרכיבים:

1. **`parallel_processor_subagent.py`**
   - SubAgent עם Send API פנימי
   - מזהה רשימות אוטומטית
   - מריץ עיבוד מקביל
   - מחזיר דוח מסכם

2. **`mcp_agent_grok.py`** (מעודכן)
   - רשום עם parallel_processor subagent
   - הסוכן יכול לקרוא לו דרך `task` tool
   - עובד בצ'אט רגיל!

3. **`langgraph.json`** (מעודכן)
   - מצביע על הGrok agent המעודכן
   - נטען אוטומטית ב-LangGraph Studio

---

## איך זה עובד?

### תרחיש דוגמה:

```
User: "חקור את 30 השירים הפופולריים של 2024"

Grok Agent מזהה: "זו משימה מורכבת עם רשימה"
              ↓
         קורא ל-task tool:
         task(
           subagent_type="parallel_processor",
           description="Research these 30 songs: ..."
         )
              ↓
    Parallel Processor SubAgent:
    1. מזהה 30 items
    2. יוצר 30 Send objects
    3. LangGraph מריץ 30 workers במקביל
    4. מצבר תוצאות
    5. מחזיר דוח מסכם
              ↓
    Grok Agent מקבל דוח ומציג למשתמש
```

### הזיהוי האוטומטי:

ה-SubAgent מזהה רשימות בפורמטים אלה:

1. **ספרות ממוספרות:**
   ```
   1. Song A
   2. Song B
   3. Song C
   ```

2. **מספר + סוג:**
   ```
   "חקור 30 שירים"
   "נתח 10 מאמרים"
   "בדוק 20 אתרים"
   ```

3. **רשימה מופרדת בפסיקים:**
   ```
   "Beatles, Rolling Stones, Pink Floyd, Led Zeppelin"
   ```

---

## איך משתמשים?

### דרך 1: הסוכן יבחר אוטומטית (מומלץ!)

פשוט תן לסוכן משימה עם רשימה:

```
User: "חקור את 10 הסרטים הטובים של 2024"
```

הסוכן **עצמו** יחליט אם להשתמש ב-parallel_processor בהתאם למשימה.

### דרך 2: בקש במפורש

תגיד לסוכן להשתמש ב-parallel processor:

```
User: "השתמש ב-parallel processor כדי לחקור את הרשימה הזו: ..."
```

או:

```
User: "הרץ את זה במקביל: ..."
```

---

## דוגמאות לשימוש

### דוגמה 1: מחקר שירים

**Input (בChat):**
```
חקור את השירים הבאים:
1. Bohemian Rhapsody - Queen
2. Stairway to Heaven - Led Zeppelin
3. Hotel California - Eagles
4. Imagine - John Lennon
5. Smells Like Teen Spirit - Nirvana
```

**מה יקרה:**
1. הGrok agent יזהה שיש רשימה של 5 items
2. יקרא ל-`task` tool עם `parallel_processor`
3. ה-SubAgent יריץ 5 workers במקביל
4. כל worker "יחקר" שיר אחד
5. התוצאות יצטברו לדוח אחד
6. הדוח יוחזר למשתמש

**Output:**
```
Parallel Processing Report
============================================================
Total items processed: 5
Successful: 5
Failed: 0

Results:
------------------------------------------------------------
[ 1] Bohemian Rhapsody - Queen
     Status: success
     Details: Processed item 1

[ 2] Stairway to Heaven - Led Zeppelin
     Status: success
     Details: Processed item 2

...
============================================================
Processing complete. 5 items processed successfully.
```

### דוגמה 2: בדיקת אתרים

**Input:**
```
בדוק את האתרים הבאים ותגיד לי אם הם זמינים:
google.com, github.com, stackoverflow.com, reddit.com, twitter.com
```

**הסוכן:**
- יזהה 5 אתרים
- יריץ 5 בדיקות במקביל
- יחזיר דוח מסכם

### דוגמה 3: ניתוח מאמרים

**Input:**
```
נתח 20 מאמרים על AI מ-2024
```

**הסוכן:**
- יזהה "20 מאמרים"
- ייצור 20 items אוטומטית
- יריץ 20 ניתוחים במקביל
- יחזיר דוח מרוכז

---

## מה ההבדל מהדוגמה הקודמת?

### לפני (parallel_music_research_agent.py):
- ❌ גרף נפרד שלא משולב בסוכן
- ❌ רק visualization, לא Chat
- ❌ צריך להריץ באופן ידני
- ❌ לא נגיש מהסוכן הרגיל

### עכשיו (parallel_processor_subagent):
- ✅ **משולב בסוכן** דרך SubAgentMiddleware
- ✅ **עובד בChat** - פשוט תשאל
- ✅ **אוטומטי** - הסוכן מחליט מתי להשתמש
- ✅ **נגיש תמיד** - חלק מה-`task` tool

---

## איך לבדוק?

### שלב 1: הרג תהליכים ישנים

פתח Task Manager (Ctrl+Shift+Esc) וסגור:
- כל `python.exe` (של langgraph)
- כל `langgraph.exe`

### שלב 2: הפעל שרת נקי

```bash
cd C:\projects\learn_ten_x_faster\deepagents
C:\Users\yesha\AppData\Local\Programs\Python\Python311\Scripts\langgraph.exe dev
```

תראה:
```
Registering 'grok_agent_with_parallel' graph...
✓ Successfully registered graph
```

### שלב 3: פתח LangGraph Studio

```
https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024
```

בחר את `grok_agent_with_parallel`

### שלב 4: בדוק ב-Chat

לחץ על **Chat** (לא Graph!)

נסה:
```
User: "חקור את 5 השירים הבאים: Song1, Song2, Song3, Song4, Song5"
```

תראה שהסוכן:
1. מזהה את הרשימה
2. קורא ל-`task` tool
3. ה-SubAgent מריץ במקביל
4. מחזיר דוח מסכם

---

## הרחבה עם כלים אמיתיים

כרגע ה-SubAgent עושה סימולציה. כדי להוסיף כלים אמיתיים:

### ערוך: `parallel_processor_subagent.py`

במקום:
```python
async def process_single_item(state: dict) -> dict:
    # Simulate processing
    await asyncio.sleep(0.5)

    result = {
        "item_id": item_id,
        "description": description,
        "result": f"Processed: {description}",
        "status": "success"
    }
```

החלף ב:
```python
async def process_single_item(state: dict) -> dict:
    # Use real Perplexity MCP
    from langchain_mcp_adapters.client import MultiServerMCPClient

    mcp_client = MultiServerMCPClient({...})
    tools = await mcp_client.get_tools()

    # Research using Perplexity
    perplexity_search = tools["perplexity_search"]
    result = await perplexity_search.ainvoke({
        "query": f"Research information about {description}"
    })

    return {"results": [{
        "item_id": item_id,
        "description": description,
        "result": result,
        "status": "success"
    }]}
```

השרת יטען אוטומטית (hot reload).

---

## Troubleshooting

### בעיה: הסוכן לא משתמש ב-parallel processor

**פתרון:**
- בקש במפורש: "השתמש ב-parallel processor"
- או תן רשימה ברורה עם "חקור X items"

### בעיה: שגיאת import

**פתרון:**
- וודא ש-`parallel_processor_subagent.py` בתיקייה הנכונה
- הרץ מהתיקייה `deepagents`

### בעיה: השרת לא רואה את הגרף

**פתרון:**
1. הרוג את כל התהליכים
2. מחק cache: `rm -rf .langgraph_cache`
3. הפעל מחדש: `langgraph dev`

---

## סיכום

עכשיו יש לך **יכולת עיבוד מקביל משולבת** בסוכן!

✅ עובד בChat mode
✅ זיהוי אוטומטי של רשימות
✅ עיבוד מקביל עם Send API
✅ משולב כמו SubAgentMiddleware
✅ משתמש בקוד רשמי של LangGraph

**השתמש בחופשיות!** 🎉
