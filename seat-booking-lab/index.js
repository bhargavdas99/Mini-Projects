const express = require('express');
const { Pool } = require('pg');

const app = express();
app.use(express.json());

// Connection pool configuration
const pool = new Pool({
  connectionString: process.env.DATABASE_URL || 'postgres://postgres:postgres@db:5432/booking_db',
  max: 10,
  idleTimeoutMillis: 30000,
});

// 1. Get all seats
app.get('/seats', async (req, res) => {
  try {
    const result = await pool.query('SELECT * FROM seats ORDER BY id ASC');
    res.json(result.rows);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Helper to simulate delay inside the transaction
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

// 2. Book a seat using SELECT ... FOR UPDATE (Two-Phase Locking)
app.post('/book', async (req, res) => {
  const { seatId, userName, holdSeconds = 0 } = req.body;

  if (!seatId || !userName) {
    return res.status(400).json({ error: 'seatId and userName are required' });
  }

  // Must checkout a dedicated client from the pool to run a multi-statement transaction
  const client = await pool.connect();

  try {
    console.log(`[REQ] ${userName} attempting to lock Seat ${seatId}...`);
    await client.query('BEGIN');

    // PHASE 1 (GROWING PHASE): Acquire exclusive row lock
    const seatQuery = await client.query(
      'SELECT id, is_booked, name FROM seats WHERE id = $1 FOR UPDATE',
      [seatId]
    );

    if (seatQuery.rows.length === 0) {
      await client.query('ROLLBACK');
      return res.status(404).json({ error: `Seat ${seatId} not found` });
    }

    const seat = seatQuery.rows[0];

    // Check if another transaction already committed a booking
    if (seat.is_booked) {
      await client.query('ROLLBACK');
      console.log(`[BLOCKED] Seat ${seatId} was already booked by ${seat.name}.`);
      return res.status(409).json({ 
        error: `Seat ${seatId} is already booked by ${seat.name}` 
      });
    }

    console.log(`[LOCKED] ${userName} holds lock on Seat ${seatId}. Simulating work for ${holdSeconds}s...`);
    if (holdSeconds > 0) {
      await sleep(holdSeconds * 1000);
    }

    // Execute update while holding the lock
    const updateResult = await client.query(
      'UPDATE seats SET is_booked = true, name = $1 WHERE id = $2 RETURNING *',
      [userName, seatId]
    );

    // PHASE 2 (SHRINKING PHASE): Commit releases all locks
    await client.query('COMMIT');
    console.log(`[COMMITTED] Seat ${seatId} successfully booked for ${userName}. Lock released.`);

    res.json({
      status: 'success',
      bookedSeat: updateResult.rows[0]
    });
  } catch (err) {
    await client.query('ROLLBACK');
    console.error(`[ERROR] Transaction aborted for ${userName}:`, err.message);
    res.status(500).json({ error: err.message });
  } finally {
    // Release the client connection back to the pool
    client.release();
  }
});

const PORT = 8080;
app.listen(PORT, () => {
  console.log(`Booking server listening on port ${PORT}`);
});