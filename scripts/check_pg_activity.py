import psycopg2
import json

def main():
    conn = psycopg2.connect(host='localhost', port=5432, user='odoo', password='odoo', dbname='odoo19_clean')
    cur = conn.cursor()
    cur.execute("SELECT pid, state, query_start, wait_event_type, query FROM pg_stat_activity WHERE state IN ('active','idle in transaction') ORDER BY query_start DESC LIMIT 50")
    rows = cur.fetchall()
    print(json.dumps(rows, default=str, ensure_ascii=False))
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
