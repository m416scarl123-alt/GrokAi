import asyncpg

POOL = None


# =========================
# ИНИЦИАЛИЗАЦИЯ БАЗЫ
# =========================

async def init_db(database_url):
    global POOL

    POOL = await asyncpg.create_pool(
        database_url,
        min_size=1,
        max_size=10
    )

    async with POOL.acquire() as c:

        await c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            telegram_id BIGINT PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            activated BOOLEAN NOT NULL DEFAULT FALSE,
            full_access BOOLEAN NOT NULL DEFAULT FALSE,
            image_access BOOLEAN NOT NULL DEFAULT FALSE,
            blocked BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            last_seen TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            requests_count BIGINT NOT NULL DEFAULT 0
        );
        """)

        # Добавляем поле в уже существующую базу,
        # если его там ещё нет.
        await c.execute("""
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS image_access
        BOOLEAN NOT NULL DEFAULT FALSE;
        """)

        await c.execute("""
        CREATE TABLE IF NOT EXISTS activation_codes (
            code TEXT PRIMARY KEY,
            uses INTEGER NOT NULL DEFAULT 0,
            max_uses INTEGER NOT NULL DEFAULT 3,
            revoked BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """)

        await c.execute("""
        CREATE TABLE IF NOT EXISTS activations (
            code TEXT NOT NULL
                REFERENCES activation_codes(code)
                ON DELETE CASCADE,

            telegram_id BIGINT NOT NULL
                REFERENCES users(telegram_id)
                ON DELETE CASCADE,

            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

            PRIMARY KEY(code, telegram_id)
        );
        """)

        await c.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id BIGSERIAL PRIMARY KEY,

            telegram_id BIGINT NOT NULL
                REFERENCES users(telegram_id)
                ON DELETE CASCADE,

            role TEXT NOT NULL,
            content TEXT NOT NULL,

            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """)

        await c.execute("""
        CREATE TABLE IF NOT EXISTS admin_codes (
            code TEXT PRIMARY KEY,
            expires_at TIMESTAMPTZ NOT NULL,
            used BOOLEAN NOT NULL DEFAULT FALSE
        );
        """)


# =========================
# ПОЛЬЗОВАТЕЛИ
# =========================

async def upsert_user(tg_user):

    async with POOL.acquire() as c:

        await c.execute("""
        INSERT INTO users(
            telegram_id,
            username,
            first_name
        )
        VALUES($1, $2, $3)

        ON CONFLICT(telegram_id)
        DO UPDATE SET
            username=EXCLUDED.username,
            first_name=EXCLUDED.first_name,
            last_seen=NOW()
        """,
        tg_user.id,
        tg_user.username,
        tg_user.first_name)


async def get_user(tg_id):

    async with POOL.acquire() as c:

        return await c.fetchrow(
            """
            SELECT *
            FROM users
            WHERE telegram_id=$1
            """,
            tg_id
        )


# =========================
# ПОЛНЫЙ ДОСТУП
# =========================

async def set_full_access(
    tg_id,
    enabled=True
):

    async with POOL.acquire() as c:

        await c.execute(
            """
            UPDATE users
            SET full_access=$2
            WHERE telegram_id=$1
            """,
            tg_id,
            enabled
        )


# =========================
# ДОСТУП К ИЗОБРАЖЕНИЯМ
# =========================

async def set_image_access(
    tg_id,
    enabled=True
):

    async with POOL.acquire() as c:

        await c.execute(
            """
            UPDATE users
            SET image_access=$2
            WHERE telegram_id=$1
            """,
            tg_id,
            enabled
        )


# =========================
# БЛОКИРОВКА
# =========================

async def set_blocked(
    tg_id,
    enabled=True
):

    async with POOL.acquire() as c:

        await c.execute(
            """
            UPDATE users
            SET blocked=$2
            WHERE telegram_id=$1
            """,
            tg_id,
            enabled
        )


# =========================
# СООБЩЕНИЯ
# =========================

async def add_message(
    tg_id,
    role,
    content,
    limit
):

    async with POOL.acquire() as c:

        await c.execute(
            """
            INSERT INTO messages(
                telegram_id,
                role,
                content
            )
            VALUES($1, $2, $3)
            """,
            tg_id,
            role,
            content
        )

        await c.execute(
            """
            DELETE FROM messages

            WHERE telegram_id=$1

            AND id NOT IN (

                SELECT id
                FROM messages

                WHERE telegram_id=$1

                ORDER BY id DESC

                LIMIT $2
            )
            """,
            tg_id,
            limit
        )


async def get_history(
    tg_id,
    limit
):

    async with POOL.acquire() as c:

        rows = await c.fetch(
            """
            SELECT role, content

            FROM messages

            WHERE telegram_id=$1

            ORDER BY id DESC

            LIMIT $2
            """,
            tg_id,
            limit
        )

    return list(
        reversed(
            [
                {
                    "role": r["role"],
                    "content": r["content"]
                }
                for r in rows
            ]
        )
    )


async def clear_history(tg_id):

    async with POOL.acquire() as c:

        await c.execute(
            """
            DELETE FROM messages
            WHERE telegram_id=$1
            """,
            tg_id
        )


# =========================
# СЧЁТЧИК ЗАПРОСОВ
# =========================

async def increment_requests(tg_id):

    async with POOL.acquire() as c:

        await c.execute(
            """
            UPDATE users

            SET requests_count =
                requests_count + 1

            WHERE telegram_id=$1
            """,
            tg_id
        )


# =========================
# КОДЫ АКТИВАЦИИ
# =========================

async def create_activation_code(
    code,
    max_uses
):

    async with POOL.acquire() as c:

        await c.execute(
            """
            INSERT INTO activation_codes(
                code,
                max_uses
            )
            VALUES($1, $2)
            """,
            code,
            max_uses
        )


async def activate_code(
    code,
    tg_id
):

    async with POOL.acquire() as c:

        async with c.transaction():

            row = await c.fetchrow(
                """
                SELECT *
                FROM activation_codes

                WHERE code=$1
                AND revoked=FALSE
                AND uses < max_uses

                FOR UPDATE
                """,
                code
            )

            if not row:
                return False, "invalid"

            exists = await c.fetchval(
                """
                SELECT 1
                FROM activations

                WHERE code=$1
                AND telegram_id=$2
                """,
                code,
                tg_id
            )

            if exists:
                return False, "already"

            await c.execute(
                """
                INSERT INTO activations(
                    code,
                    telegram_id
                )
                VALUES($1, $2)
                """,
                code,
                tg_id
            )

            await c.execute(
                """
                UPDATE activation_codes

                SET uses=uses+1

                WHERE code=$1
                """,
                code
            )

            await c.execute(
                """
                UPDATE users

                SET activated=TRUE

                WHERE telegram_id=$1
                """,
                tg_id
            )

            return True, "ok"


async def revoke_code(code):

    async with POOL.acquire() as c:

        await c.execute(
            """
            UPDATE activation_codes

            SET revoked=TRUE

            WHERE code=$1
            """,
            code
        )


async def list_codes():

    async with POOL.acquire() as c:

        return await c.fetch(
            """
            SELECT
                code,
                uses,
                max_uses,
                revoked,
                created_at

            FROM activation_codes

            ORDER BY created_at DESC

            LIMIT 100
            """
        )


# =========================
# СТАТИСТИКА
# =========================

async def stats():

    async with POOL.acquire() as c:

        return await c.fetchrow(
            """
            SELECT

                COUNT(*) AS users,

                COUNT(*)
                FILTER(
                    WHERE activated
                ) AS activated,

                COUNT(*)
                FILTER(
                    WHERE full_access
                ) AS full_access,

                COUNT(*)
                FILTER(
                    WHERE image_access
                ) AS image_access,

                COUNT(*)
                FILTER(
                    WHERE blocked
                ) AS blocked,

                COALESCE(
                    SUM(requests_count),
                    0
                ) AS requests

            FROM users
            """
        )


# =========================
# КОДЫ АДМИНИСТРАТОРА
# =========================

async def save_admin_code(
    code,
    expires_at
):

    async with POOL.acquire() as c:

        await c.execute(
            """
            INSERT INTO admin_codes(
                code,
                expires_at
            )
            VALUES($1, $2)
            """,
            code,
            expires_at
        )


async def consume_admin_code(code):

    async with POOL.acquire() as c:

        row = await c.fetchrow(
            """
            SELECT *

            FROM admin_codes

            WHERE code=$1
            AND used=FALSE
            AND expires_at > NOW()

            FOR UPDATE
            """,
            code
        )

        if not row:
            return False

        await c.execute(
            """
            UPDATE admin_codes

            SET used=TRUE

            WHERE code=$1
            """,
            code
        )

        return True
