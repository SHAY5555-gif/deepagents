# הוראות הפעלת Parallel Agent ב-LangGraph Studio

## הבעיה הנוכחית
יש מספר שרתי LangGraph רצים במקביל על פורט 2024, והדפדפן מתחבר לשרת ישן.

## פתרון מהיר:

### שלב 1: עצור את כל התהליכים
פתח Task Manager (Ctrl+Shift+Esc) וסגור את כל התהליכים:
- `python.exe` (שקשורים ל-langgraph)
- `langgraph.exe`

### שלב 2: הפעל שרת נקי
פתח PowerShell או CMD בתיקייה:
```
cd C:\projects\learn_ten_x_faster\deepagents
```

הרץ:
```
C:\Users\yesha\AppData\Local\Programs\Python\Python311\Scripts\langgraph.exe dev
```

### שלב 3: פתח דפדפן
לך ל:
```
https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024
```

### שלב 4: בחר את parallel_music_research
במסך Studio, לחץ על הדרופדאון של הגרפים ובחר `parallel_music_research`

## איך להריץ את הסוכן:

### Input לדוגמה:
בחלק ה-Input, שנה את Messages ל:
```yaml
- role: user
  content: "חפש מידע על 10 שירים"
```

או בתור JSON:
```json
{
  "messages": [
    {
      "role": "user",
      "content": "חפש מידע על 10 שירים"
    }
  ]
}
```

### לחץ Submit
הסוכן יריץ 10 סוכנים במקביל!

## מה תראה:
1. **Graph visualization** - הגרף עם כל ה-nodes
2. **Parallel execution** - תראה decompose → 10 parallel agents → aggregate
3. **Timeline** - תראה שהכל רץ במקביל (לא סדרתי)
4. **State** - תראה את כל התוצאות מ-10 הסוכנים

## שינוי מספר הסוכנים:
ערוך את הקובץ `parallel_music_research_agent.py` בשורה 68:
```python
songs = [
    {"id": i, "title": f"Song {i}", "artist": f"Artist {i}"}
    for i in range(1, 31)  # שנה ל-100 עבור 100 סוכנים!
]
```

השרת יטען אוטומטית את השינוי (hot reload).

## Troubleshooting:

### אם לא רואה את parallel_music_research:
1. וודא ש-`langgraph.json` מכיל רק:
```json
{
  "dependencies": ["."],
  "graphs": {
    "parallel_music_research": "./parallel_music_research_agent.py:agent"
  },
  "env": ".env"
}
```

2. רענן את הדפדפן (Ctrl+F5)

### אם יש שגיאות:
בדוק את הלוגים בטרמינל שבו רץ השרת.

---

**זהו! עכשיו יש לך גישה מלאה ל-LangGraph Studio עם הסוכן המקביל! 🎉**
