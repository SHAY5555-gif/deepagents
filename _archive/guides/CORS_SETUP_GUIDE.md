# הדרכה להגדרת CORS עבור LangGraph

## הבעיה
LangGraph לא כולל הגדרות CORS כברירת מחדל, מה שמונע גישה מדפדפן ויוצר שגיאות כמו:
- `Access to fetch at 'http://localhost:8123/...' from origin 'http://localhost:3000' has been blocked by CORS policy`

## הפתרון
יצרנו proxy server שמוסיף headers של CORS לכל הבקשות של LangGraph.

## דרכי שימוש

### אופציה 1: השתמש ב-Simple API Server (עבור parallel agents)

אם אתה עובד עם parallel agents, השתמש בשרת המוכן:

```bash
python simple_api_server.py
```

השרת יעלה על `http://localhost:8000` עם CORS מופעל.

### אופציה 2: השתמש ב-CORS Proxy עבור LangGraph

לשימוש עם כל סוגי ה-agents של LangGraph:

1. **הפעל את LangGraph** (בטרמינל ראשון):
   ```bash
   langgraph up
   ```
   השרת יעלה על `http://localhost:8123`

2. **הפעל את ה-CORS Proxy** (בטרמינל שני):

   **Windows (Batch):**
   ```bash
   start_cors_server.bat
   ```

   **Windows (PowerShell):**
   ```powershell
   .\start_cors_server.ps1
   ```

   **או ישירות:**
   ```bash
   python langgraph_server_with_cors.py
   ```

   השרת יעלה על `http://localhost:8080` עם CORS מופעל.

3. **חבר את האפליקציה שלך ל-`http://localhost:8080`** במקום ל-8123

## איך זה עובד

```
Browser → :8080 (CORS Proxy) → :8123 (LangGraph)
         ↑                     ↓
         └─ CORS Headers Added ┘
```

הפרוקסי:
1. מקבל בקשות מהדפדפן על פורט 8080
2. מעביר אותן ל-LangGraph על פורט 8123
3. מוסיף CORS headers לתגובה
4. מחזיר לדפדפן עם הרשאות CORS

## הגדרות CORS

השרת מגדיר:
- `allow_origins=["*"]` - מאפשר גישה מכל מקור
- `allow_methods=["*"]` - מאפשר כל סוגי הבקשות (GET, POST, PUT, DELETE וכו')
- `allow_headers=["*"]` - מאפשר כל headers
- `allow_credentials=True` - מאפשר שליחת cookies

## בדיקת תקינות

בדוק שהכל עובד:

1. **בדוק ש-LangGraph רץ:**
   ```bash
   curl http://localhost:8123/health
   ```

2. **בדוק שה-CORS Proxy רץ:**
   ```bash
   curl http://localhost:8080/health
   ```

3. **בדוק CORS מהדפדפן:**
   פתח Console בדפדפן והרץ:
   ```javascript
   fetch('http://localhost:8080/health')
     .then(r => r.json())
     .then(console.log)
   ```

## בעיות נפוצות

### "Cannot connect to LangGraph server"
- וודא ש-LangGraph רץ על פורט 8123
- הרץ `langgraph up` לפני הפעלת הפרוקסי

### "Port 8080 already in use"
- שנה את הפורט בקובץ `langgraph_server_with_cors.py`
- או סגור את התהליך שמשתמש בפורט 8080

### עדיין מקבל שגיאות CORS
- וודא שאתה מתחבר ל-8080 ולא ל-8123
- נקה cache של הדפדפן
- בדוק ב-Network tab שה-headers של CORS מגיעים

## התאמה אישית

לשינוי הגדרות, ערוך את `langgraph_server_with_cors.py`:

```python
# לשינוי הפורט של הפרוקסי
port=8080  # שנה למספר אחר

# לשינוי כתובת LangGraph
LANGGRAPH_URL = "http://localhost:8123"  # שנה אם LangGraph רץ במקום אחר

# להגבלת מקורות ספציפיים (במקום כולם)
allow_origins=["http://localhost:3000", "http://localhost:3001"]
```

## אבטחה

⚠️ **אזהרה**: ההגדרות הנוכחיות מאפשרות גישה מכל מקור (`*`).
בסביבת ייצור, הגבל למקורות ספציפיים:

```python
allow_origins=["https://your-domain.com"]
```