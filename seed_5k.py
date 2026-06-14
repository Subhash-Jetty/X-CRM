"""
Direct Supabase seeder — 5000 customers + 15000 orders using psycopg2 (sync, no pooler issues).
Run: .\venv\Scripts\python.exe seed_5k.py
"""
import json
import random
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import psycopg2
import psycopg2.extras

# Direct connection (port 5432 = direct, not 6543 = pooler)
DSN = "postgresql://postgres.euntouwflhlzgegmmxgj:YxcL7pYFbGqbceA4@aws-1-ap-south-1.pooler.supabase.com:5432/postgres"

FIRST = ["Amit","Priya","Rahul","Sneha","Vikram","Ananya","Rohit","Neha","Arjun","Kavya","Sanjay","Divya","Karan","Pooja","Aditya","Riya","Manish","Simran","Nikhil","Megha","Suresh","Deepika","Rajesh","Nisha","Varun","Isha","Ajay","Swati","Pranav","Tanvi","Harsh","Shruti","Gaurav","Meera","Akash","Ritika","Dev","Pallavi","Kunal","Aditi","Siddharth","Bhavna","Vivek","Anjali","Rohan","Sakshi","Mohit","Kriti","Yash","Tanya","Abhishek","Madhuri","Vishal","Preeti","Tushar","Komal","Mayank","Sonam","Ravi","Chitra"]
LAST = ["Sharma","Patel","Singh","Gupta","Kumar","Mehta","Joshi","Verma","Reddy","Nair","Chopra","Bhat","Iyer","Rao","Malhotra","Shah","Mishra","Chauhan","Agarwal","Sinha","Banerjee","Das","Desai","Kulkarni","Menon","Saxena","Thakur","Pandey","Tiwari","Bhatt"]
TAGS = ["coffee-lover","frequent-buyer","weekend-visitor","app-user","loyalty-member","new-customer","premium","morning-regular","bulk-buyer","gift-shopper","seasonal","referral"]
ITEMS = [("Espresso",180),("Cappuccino",250),("Cold Brew",280),("Latte",220),("Mocha",300),("Americano",200),("Flat White",260),("Macchiato",240),("Affogato",320),("Croissant",150),("Muffin",120),("Sandwich",250),("Cookie Pack",180),("Brownie",160),("Cheesecake Slice",280),("Bagel",140),("Scone",130),("Granola Bowl",220)]
CHANNELS = ["online","in-store","app"]
DOMAINS = ["gmail.com","yahoo.com","outlook.com","hotmail.com","company.in"]

NUM_CUST = 5000
NUM_ORD = 15000
CHUNK = 500

def main():
    now = datetime.now(timezone.utc)

    # Generate customers
    print(f"Generating {NUM_CUST} customers...")
    customers = []
    emails = set()
    for i in range(NUM_CUST):
        f, l = random.choice(FIRST), random.choice(LAST)
        e = f"{f.lower()}.{l.lower()}{i}@{random.choice(DOMAINS)}"
        while e in emails:
            e = f"{f.lower()}{random.randint(1,99999)}@{random.choice(DOMAINS)}"
        emails.add(e)
        customers.append((
            str(uuid4()), f"{f} {l}", e,
            f"+91{random.randint(7000000000,9999999999)}",
            json.dumps(random.sample(TAGS, k=random.randint(0,4))),
            0, 0, 0,
            now - timedelta(days=random.randint(1,365)),
            now,
        ))

    # Generate orders
    print(f"Generating {NUM_ORD} orders...")
    orders = []
    for _ in range(NUM_ORD):
        c = random.choice(customers)
        items = []
        total = 0
        for _ in range(random.randint(1,4)):
            name, price = random.choice(ITEMS)
            qty = random.randint(1,3)
            items.append({"name": name, "price": price, "quantity": qty})
            total += price * qty
        orders.append((
            str(uuid4()), c[0], total,
            json.dumps(items), random.choice(CHANNELS), "completed",
            now - timedelta(days=random.randint(0,180), hours=random.randint(0,23)),
        ))

    conn = psycopg2.connect(DSN)
    conn.autocommit = False
    cur = conn.cursor()

    try:
        # Insert customers
        print("Inserting customers...")
        cust_sql = """
            INSERT INTO customers (id, name, email, phone, tags, total_spend, order_count, avg_order_value, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s)
            ON CONFLICT (email) DO UPDATE SET name=EXCLUDED.name, phone=EXCLUDED.phone, tags=EXCLUDED.tags, updated_at=EXCLUDED.updated_at
        """
        for i in range(0, len(customers), CHUNK):
            chunk = customers[i:i+CHUNK]
            psycopg2.extras.execute_batch(cur, cust_sql, chunk, page_size=CHUNK)
            conn.commit()
            print(f"  Customers: {min(i+CHUNK, len(customers))}/{len(customers)}")

        # Insert orders
        print("Inserting orders...")
        ord_sql = """
            INSERT INTO orders (id, customer_id, amount, items, channel, status, created_at)
            VALUES (%s, %s, %s, %s::jsonb, %s, %s, %s)
            ON CONFLICT (id) DO NOTHING
        """
        for i in range(0, len(orders), CHUNK):
            chunk = orders[i:i+CHUNK]
            psycopg2.extras.execute_batch(cur, ord_sql, chunk, page_size=CHUNK)
            conn.commit()
            print(f"  Orders: {min(i+CHUNK, len(orders))}/{len(orders)}")

        # Bulk aggregate
        print("Updating customer aggregates (single query)...")
        cur.execute("""
            UPDATE customers c SET
                order_count = s.cnt,
                total_spend = s.total,
                avg_order_value = CASE WHEN s.cnt > 0 THEN s.total / s.cnt ELSE 0 END,
                first_order_date = s.first_dt,
                last_order_date = s.last_dt,
                updated_at = NOW()
            FROM (
                SELECT customer_id, COUNT(*) as cnt, SUM(amount) as total,
                       MIN(created_at) as first_dt, MAX(created_at) as last_dt
                FROM orders GROUP BY customer_id
            ) s WHERE c.id = s.customer_id
        """)
        conn.commit()

        print(f"\nDone! Seeded {NUM_CUST} customers + {NUM_ORD} orders with aggregates!")

    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    main()
