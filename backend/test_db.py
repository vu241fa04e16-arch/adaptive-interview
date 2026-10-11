
import asyncio
import asyncpg

async def main():
    conn = None
    try:
        conn = await asyncpg.connect(
            "postgresql://postgres:root@localhost:5432/adaptive_interview"
        )
        database = await conn.fetchval("SELECT current_database()")
        print("SUCCESS: Connected to database:", database)

    except Exception as error:
        print("FAILED:", type(error).__name__, error)

    finally:
        if conn is not None:
            await conn.close()

asyncio.run(main())