const express = require('express');
const mysql = require('mysql2/promise');
const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');
const crypto = require('crypto');
const path = require('path');
const dotenv = require('dotenv');

dotenv.config();

const app = express();
const port = 3000;

// Middleware
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

// Database connection pool
const pool = mysql.createPool({
    host: process.env.DB_HOST,
    port: process.env.DB_PORT,
    user: process.env.DB_USER,
    password: process.env.DB_PASSWORD,
    database: process.env.DB_NAME,
    waitForConnections: true,
    connectionLimit: 10,
    queueLimit: 0
});

// Email validation regex
const emailRegex = /^[\w-\.]+@([\w-]+\.)+[\w-]{2,4}$/;

// Serve HTML pages
app.get('/login', (req, res) => {
    res.sendFile(path.join(__dirname, 'public', 'login.html'));
});

app.get('/signup', (req, res) => {
    res.sendFile(path.join(__dirname, 'public', 'signup.html'));
});

app.get('/forgot-password', (req, res) => {
    res.sendFile(path.join(__dirname, 'public', 'forget.html'));
});

// Placeholder for profile page (since login redirects to /profile)
app.get('/profile', (req, res) => {
    res.send('<h1>Welcome to your profile!</h1><a href="/login">Logout</a>');
});

// Signup endpoint
app.post('/signup', async (req, res) => {
    const { username, email, password, confirmPassword } = req.body;

    if (!username || !email || !password || !confirmPassword) {
        return res.status(400).json({ message: 'All fields are required' });
    }

    if (!emailRegex.test(email)) {
        return res.status(400).json({ message: 'Invalid email address' });
    }

    if (password !== confirmPassword) {
        return res.status(400).json({ message: 'Passwords do not match' });
    }

    if (password.length < 8) {
        return res.status(400).json({ message: 'Password must be at least 8 characters long' });
    }

    try {
        const connection = await pool.getConnection();
        const [rows] = await connection.query('SELECT email FROM users WHERE email = ?', [email]);

        if (rows.length > 0) {
            connection.release();
            return res.status(400).json({ message: 'Email already registered' });
        }

        const hashedPassword = await bcrypt.hash(password, 10);
        await connection.query(
            'INSERT INTO users (username, email, password) VALUES (?, ?, ?)',
            [username, email, hashedPassword]
        );

        connection.release();
        res.status(201).json({ message: 'Registration successful! Please log in.' });
    } catch (error) {
        console.error('Signup error:', error);
        res.status(500).json({ message: 'Server error' });
    }
});

// Login endpoint
app.post('/login', async (req, res) => {
    const { email, password } = req.body;

    if (!email || !password) {
        return res.status(400).json({ message: 'Email and password are required' });
    }

    try {
        const connection = await pool.getConnection();
        const [rows] = await connection.query('SELECT id, username, email, password FROM users WHERE email = ?', [email]);

        if (rows.length === 0) {
            connection.release();
            return res.status(401).json({ message: 'Invalid email or password' });
        }

        const user = rows[0];
        const isMatch = await bcrypt.compare(password, user.password);

        if (!isMatch) {
            connection.release();
            return res.status(401).json({ message: 'Invalid email or password' });
        }

        const token = jwt.sign(
            { id: user.id, email: user.email },
            process.env.SECRET_KEY,
            { expiresIn: '1h' }
        );

        connection.release();
        res.status(200).json({ message: 'Login successful', token });
    } catch (error) {
        console.error('Login error:', error);
        res.status(500).json({ message: 'Server error' });
    }
});

// Forgot password endpoint
app.post('/forgot-password', async (req, res) => {
    const { email } = req.body;

    if (!email) {
        return res.status(400).json({ message: 'Email is required' });
    }

    if (!emailRegex.test(email)) {
        return res.status(400).json({ message: 'Invalid email address' });
    }

    try {
        const connection = await pool.getConnection();
        const [rows] = await connection.query('SELECT id FROM users WHERE email = ?', [email]);

        if (rows.length === 0) {
            connection.release();
            return res.status(404).json({ message: 'Email not found' });
        }

        // Generate reset token
        const token = crypto.randomBytes(32).toString('hex');
        const expiresAt = new Date(Date.now() + 15 * 60 * 1000); // 15 minutes expiry

        await connection.query(
            'INSERT INTO password_resets (email, token, expires_at) VALUES (?, ?, ?)',
            [email, token, expiresAt]
        );

        connection.release();
        res.status(200).json({ message: 'Reset token generated successfully.', token });
    } catch (error) {
        console.error('Forgot password error:', error);
        res.status(500).json({ message: 'Server error' });
    }
});

// Reset password endpoint
app.post('/reset-password', async (req, res) => {
    const { email, token, newPassword, confirmPassword } = req.body;

    if (!email || !token || !newPassword || !confirmPassword) {
        return res.status(400).json({ message: 'All fields are required' });
    }

    if (newPassword !== confirmPassword) {
        return res.status(400).json({ message: 'Passwords do not match' });
    }

    if (newPassword.length < 8) {
        return res.status(400).json({ message: 'Password must be at least 8 characters long' });
    }

    try {
        const connection = await pool.getConnection();
        const [rows] = await connection.query(
            'SELECT id, expires_at FROM password_resets WHERE email = ? AND token = ?',
            [email, token]
        );

        if (rows.length === 0) {
            connection.release();
            return res.status(400).json({ message: 'Invalid or expired token' });
        }

        const resetRecord = rows[0];
        if (new Date() > new Date(resetRecord.expires_at)) {
            connection.release();
            return res.status(400).json({ message: 'Token has expired' });
        }

        const hashedPassword = await bcrypt.hash(newPassword, 10);
        await connection.query(
            'UPDATE users SET password = ? WHERE email = ?',
            [hashedPassword, email]
        );

        await connection.query(
            'DELETE FROM password_resets WHERE email = ? AND token = ?',
            [email, token]
        );

        connection.release();
        res.status(200).json({ message: 'Password reset successful' });
    } catch (error) {
        console.error('Reset password error:', error);
        res.status(500).json({ message: 'Server error' });
    }
});

// Start server
app.listen(port, () => {
    console.log(`Server running at http://localhost:${port}`);
});