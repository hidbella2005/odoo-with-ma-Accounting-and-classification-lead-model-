import psycopg2
import json

def main():
    conn = psycopg2.connect(host='localhost', port=5432, user='odoo', password='odoo', dbname='odoo19_clean')
    cur = conn.cursor()
    cur.execute("SELECT a.pid, a.state, a.query_start, a.query, l.locktype, l.mode, l.granted FROM pg_locks l JOIN pg_stat_activity a ON l.pid = a.pid WHERE l.relation = (SELECT oid FROM pg_class WHERE relname='ir_module_module') ORDER BY a.query_start DESC LIMIT 50")
    rows = cur.fetchall()
    print(json.dumps(rows, default=str, ensure_ascii=False))
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
