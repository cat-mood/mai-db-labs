# Индексы
|test_name|query|without_index_time_ms|btree_time_ms|gin_time_ms|brin_time_ms|btree_speedup|gin_speedup|brin_speedup|notes|
|---------|-----|---------------------|-------------|-----------|------------|-------------|-----------|------------|-----|
|Диапазон цен|price_eur BETWEEN 10000 AND 20000|923.544000|899.283000|||1.0269781592668826|||B-tree для денежных значений|
|Поиск по марке и модели|maker = 'ford' AND model = 'focus'|194.622000|5.380000|629.193000||36.1750929368029740|0.30932003375752749951||GIN для полнотекстового поиска или B-tree|
|Диапазон пробега|mileage BETWEEN 100000 AND 150000|172.152000|41.039000||308.666000|4.1948390555325422||0.55772906636947380016|B-tree должен быть лучшим для числовых диапазонов|
|Точный год выпуска|manufacture_year = 2015|156.367000|25.089000||267.685000|6.2324923273147595||0.58414554420307450922|B-tree или BRIN для целых чисел|
|Диапазон дат создания|date_created BETWEEN '2015-01-01' AND '2015-12-31'|255.269000|121.883000||413.129000|2.0943773947146033||0.61789174809805169814|BRIN эффективен для временных данных|

Можно увидеть, что BRIN работает медленней, чем полное сканирование таблицы.
Основные причины замедления:
1. Некоррелированные данные
    - BRIN эффективен ТОЛЬКО если данные физически отсортированы на диске
    - Пример: если записи с manufacture_year=2020 разбросаны по всей таблице, BRIN будет бесполезен

2. Маленькие таблицы
    - Для таблиц < 1M строк BRIN часто проигрывает seq scan
    - PostgreSQL считает полное сканирование выгоднее для маленьких объемов

# Транзакции

## Внедрённые транзакции

1. Обновление времени просмотра автомобиля по id
    ```sql
    begin;
    update cars set date_last_seen = now() where id = 1;
    commit;
    ```
2. Изменение цены автомобиля по id
    ```sql
    begin;
    update cars set price = 10000 where id = 1;
    commit;
    ```

## Аномалии

|  Isolation Level  |       Dirty Read       | Nonrepeatable Read |      Phantom Read      | Serialization Anomaly |
|-------------------|------------------------|--------------------|------------------------|-----------------------|
|  Read uncommitted | Allowed, but not in PG |      Possible      |       Possible         |        Possible       |
|  Read committed   |      Not possible      |      Possible      |       Possible         |        Possible       |
|  Repeatable read  |      Not possible      |     Not possible   | Allowed, but not in PG |        Possible       |
|   Serializable    |      Not possible      |     Not possible   |      Not possible      |      Not possible     |

1. Аномалия Dirty Read

«Грязное чтение» (Dirty Read) — когда данные, которые я прочитал, кто-то может откатить ещё до того, как я завершу свою транзакцию.

> В PostgreSQL невозможно dirty read

2. Аномалия Nonrepeatable Read

    «Неповторяющееся чтение» (Non‑repeatable Read или Fuzzy Read) — когда данные, которые я прочитал, кто‑то может изменить ещё до того, как я завершу свою транзакцию.

    Возможна на уровнях изоляции: read uncommited, read commited

    ```sql
    -- Сессия 1 / Nonrepeatable read
    BEGIN TRANSACTION ISOLATION LEVEL READ COMMITTED;
    UPDATE cars SET price_eur = 15000 WHERE id = 1;
    SELECT price_eur FROM cars WHERE id = 1; -- Вернёт 15 000
    -- Оставить транзакцию открытой
    SELECT price_eur FROM cars WHERE id = 1; -- Теперь вернет 11 000
    COMMIT;
    ```

    ```sql
    -- Сессия 2 / Nonrepeatable Read
    BEGIN;
    UPDATE cars SET price_eur = 11000 WHERE id = 1;
    COMMIT;
    ```

    ```sql
    -- Сессия 1 / Nonrepeatable Read solved
    BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ;
    SELECT price_eur FROM cars WHERE id = 1; -- Вернет 11 000
    -- Оставить транзакцию открытой
    SELECT price_eur FROM cars WHERE id = 1; -- Все еще вернет 11 000
    COMMIT;
    ```

    ```sql
    -- Сессия 2 / Nonrepeatable Read solved
    BEGIN;
    UPDATE cars SET price_eur = 12000 WHERE id = 1;
    COMMIT;
    ```

3. Аномалия Phantom Read

    «Фантомное чтение» (Phantom Read) — когда ряд данных, которые я прочитал, кто‑то может изменить до того, как я завершу свою транзакцию.

    Возможна на уровнях изоляции: read uncommited, read committed, repeatable read*

    > *В PostgreSQL невозможно

    ```sql
    -- Сессия 1 / Phantom Read
    BEGIN TRANSACTION ISOLATION LEVEL read committed;
    SELECT count(*) FROM cars WHERE price_eur < money(10); -- Вернет 10 815
    -- Оставить транзакцию открытой
    UPDATE cars SET date_last_seen = now() WHERE price_eur < money(10); -- Обновит 10 816 записи!
    ROLLBACK;
    ```

    ```sql
    -- Сессия 2 / Phantom Read
    BEGIN;
    INSERT INTO cars (maker, model, price_eur) VALUES ('bmw', 'x5', 5);
    COMMIT;
    ```

    ```sql
    -- Сессия 1 / Phantom Read solved
    BEGIN TRANSACTION ISOLATION LEVEL serializable;
    SELECT count(*) FROM cars WHERE price_eur < money(10); -- Вернет 10 816
    -- Оставить транзакцию открытой
    UPDATE cars SET date_last_seen = now() WHERE price_eur < money(10); -- Обновит 10 816 записи!
    ROLLBACK;
    ```

    ```sql
    -- Сессия 2 / Phantom Read
    BEGIN;
    INSERT INTO cars (maker, model, price_eur) VALUES ('bmw', 'x5', 5);
    COMMIT;
    ```

4. Аномалия serializable

    Аномалия сериализации - это когда результат выполнения параллельных транзакций отличается от такового при их последовательном выполнении.

    Возможна на уровнях изоляции: read uncommited, read committed, repeatable read

    ```sql
    -- Сессия 1 / Serializable Anomaly
    BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ;
    SELECT SUM(price_eur) FROM cars; -- Вернет $8,337,070,704,873.17
    -- Оставить транзакцию открытой
    INSERT INTO cars (maker, model, price_eur) VALUES ('volvo', 's60', 28000);
    COMMIT; -- Тоже успешно, хотя логика суммы нарушена
    ```

    ```sql
    -- Сессия 2 / Serializable Anomaly
    begin;
    SELECT SUM(price_eur) FROM cars; -- Вернет $8,337,070,704,873.17
    INSERT INTO cars (maker, model, price_eur) VALUES ('skoda', 'octavia', 18000);
    COMMIT; -- Успешно
    ```

    ```sql
    -- Сессия 1 / Serializable Anomaly solved
    BEGIN TRANSACTION ISOLATION LEVEL serializable;
    SELECT SUM(price_eur) FROM cars; -- Вернет $8,337,070,750,873.17
    -- Оставить транзакцию открытой
    INSERT INTO cars (maker, model, price_eur) VALUES ('volvo', 's60', 28000);
    COMMIT; -- Одна из транзакций получит ошибку сериализации
    ```

    ```sql
    -- Сессия 2 / Serializable Anomaly solved
    begin TRANSACTION ISOLATION LEVEL serializable;
    SELECT SUM(price_eur) FROM cars; -- Вернет $8,337,070,704,873.17
    INSERT INTO cars (maker, model, price_eur) VALUES ('skoda', 'octavia', 18000);
    COMMIT; -- Успешно
    ```

# Использование расширений PostgreSQL для полнотекстового поиска и криптографических операций

```sql
-- Индекс pg_trgm (триграммный)
CREATE INDEX idx_cars_search_trgm ON cars 
USING gin (search_text gin_trgm_ops);

-- Индекс pg_bigm (биграммный)
CREATE INDEX idx_cars_search_bigm ON cars 
USING gin (search_text gin_bigm_ops);

-- Поиск с опечатками по триграммам (триграммы лучше справляются с ошибками)
explain analyse
SELECT id, maker, model, 
       similarity(search_text, 'toyta camri 2020') AS score
FROM cars 
WHERE search_text % 'tayata capri 2020'
ORDER BY score DESC
LIMIT 5;

--Planning Time: 1.324 ms
--Execution Time: 593.633 ms

-- Поиск с опечатками по биграммам (триграммы лучше справляются с ошибками)
explain analyse
SELECT id, maker, model, 
       similarity(search_text, 'toyta') AS score
FROM cars 
WHERE search_text =% 'tayata capri 2020'
ORDER BY score DESC
LIMIT 5;

--Planning Time: 0.365 ms
--Execution Time: 8080.525 ms


```

Сравнение pg_trgm и pg_bigm
Плюсы pg_trgm:
- Лучше находит совпадения при опечатках
- Поддерживает более гибкий поиск
- Хорошо работает с короткими строками

Минусы pg_trgm:
- Больший размер индекса
- Медленнее при точных совпадениях

Плюсы pg_bigm:
- Быстрее при точных совпадениях
- Меньший размер индекса
- Лучше для длинных текстов

Минусы pg_bigm:
- Менее терпим к опечаткам
- Требует больше ресурсов при создании индекса

```sql
-- Добавляем зашифрованные поля
ALTER TABLE cars ADD COLUMN owner_phone_encrypted BYTEA;
ALTER TABLE cars ADD COLUMN vin_encrypted BYTEA;

-- Шифруем данные при вставке
UPDATE cars SET 
  owner_phone_encrypted = pgp_sym_encrypt('+1234567890', 'my_secret_key'),
  vin_encrypted = pgp_sym_encrypt('XTA210990Y2765432', 'my_secret_key')
where id = 1;

-- Только для авторизованных пользователей
SELECT id, maker, model,
       pgp_sym_decrypt(owner_phone_encrypted::bytea, 'my_secret_key') AS owner_phone,
       pgp_sym_decrypt(vin_encrypted::bytea, 'my_secret_key') AS vin
FROM cars
WHERE id = 1;
```

Оценка влияния pgcrypto на безопасность
Плюсы:
- Данные шифруются на уровне БД
- Ключи шифрования хранятся отдельно от данных
- Поддержка стойких алгоритмов шифрования (AES, Blowfish)
- Возможность использования асимметричного шифрования

Минусы:
- Затраты на шифрование/дешифрование (5-15% производительности)
- Сложность управления ключами
- Потеря ключа = потеря данных
- Ограниченные возможности поиска по зашифрованным данным
