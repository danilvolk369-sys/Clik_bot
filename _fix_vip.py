import asyncio, aiosqlite

async def main():
    db = await aiosqlite.connect('clicktohn.db')
    await db.execute(
        'UPDATE users SET vip_multiplier_income = 1.5 WHERE user_id = 8275665893 AND vip_type = ?',
        ('VIP',)
    )
    await db.commit()
    cur = await db.execute(
        'SELECT vip_type, vip_multiplier_click, vip_multiplier_income FROM users WHERE user_id = 8275665893'
    )
    r = await cur.fetchone()
    print('Updated:', r)
    await db.close()

asyncio.run(main())
