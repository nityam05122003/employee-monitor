# Run

```bash
cd /Users/nityanandshukla/Downloads/projects/employee-monitor/backend
./run.sh
```

```bash
cd /Users/nityanandshukla/Downloads/projects/employee-monitor/frontend
npm run dev
```

# Stop

```bash
kill -9 $(lsof -ti:8003) 2>/dev/null
kill -9 $(lsof -ti:5173) 2>/dev/null
```
