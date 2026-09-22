-- Create table
CREATE TABLE IF NOT EXISTS seats(
    id int PRIMARY KEY,
    name text,
    is_booked boolean DEFAULT false NOT NULL
);

-- Seed 50 ready to book seats
INSERT INTO seats (id, name, is_booked)
select 
s.i as id,
NULL as name,
false as is_booked
FROM generate_series(1, 50) as s(i);