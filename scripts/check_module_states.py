import psycopg2, json

def main():
    conn = psycopg2.connect(host='localhost', port=5432, user='odoo', password='odoo', dbname='odoo19_clean')
    cur = conn.cursor()
    cur.execute("SELECT name, state, latest_version FROM ir_module_module WHERE state <> 'uninstalled' ORDER BY name")
    rows = cur.fetchall()
    print(json.dumps(rows, default=str, ensure_ascii=False))
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
