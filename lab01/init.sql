CREATE TABLE IF NOT EXISTS cars (
    maker VARCHAR,
    model VARCHAR,
    mileage INTEGER,
    manufacture_year INTEGER,
    engine_displacement INTEGER,
    engine_power INTEGER,
    body_type VARCHAR,
    color_slug VARCHAR,
    stk_year INTEGER,
    transmission VARCHAR,
    door_count INTEGER,
    seat_count INTEGER,
    fuel_type VARCHAR,
    date_created TIMESTAMP,
    date_last_seen TIMESTAMP,
    price_eur MONEY
);

COPY cars (maker, model, mileage, manufacture_year, engine_displacement, engine_power,
           body_type, color_slug, stk_year, transmission, door_count, seat_count, fuel_type,
           date_created, date_last_seen, price_eur)
FROM '/docker-entrypoint-initdb.d/dataset_extended.csv' DELIMITER ',' CSV HEADER;
