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

// Test database connection
pool.getConnection()
    .then(connection => {
        console.log('Database connected');
        connection.release();
    })
    .catch(err => {
        console.error('Database connection failed:', err.message, err.stack);
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

// Placeholder for profile page
app.get('/profile', (req, res) => {
    res.send('<h1>Welcome to your profile!</h1><a href="/login">Logout</a>');
});

// Signup endpoint
app.post('/signup', async (req, res) => {
    const { username, email, password, confirmPassword } = req.body;
    console.log('Signup request:', { username, email, password: '****', confirmPassword: '****' });

    if (!username || !email || !password || !confirmPassword) {
        console.log('Missing fields');
        return res.status(400).json({ message: 'All fields are required' });
    }

    if (!emailRegex.test(email)) {
        console.log('Invalid email:', email);
        return res.status(400).json({ message: 'Invalid email address' });
    }

    if (password !== confirmPassword) {
        console.log('Passwords do not match');
        return res.status(400).json({ message: 'Passwords do not match' });
    }

    if (password.length < 8) {
        console.log('Password too short');
        return res.status(400).json({ message: 'Password must be at least 8 characters long' });
    }

    try {
        const connection = await pool.getConnection();
        console.log('Database connection acquired for signup');

        const [rows] = await connection.query('SELECT email FROM users WHERE email = ?', [email]);
        if (rows.length > 0) {
            console.log('Email already registered:', email);
            connection.release();
            return res.status(400).json({ message: 'Email already registered' });
        }

        const hashedPassword = await bcrypt.hash(password, 10);
        console.log('Password hashed');

        await connection.query(
            'INSERT INTO users (username, email, password) VALUES (?, ?, ?)',
            [username, email, hashedPassword]
        );
        console.log('User inserted:', email);

        connection.release();
        res.status(201).json({ message: 'Registration successful! Please log in.' });
    } catch (error) {
        console.error('Signup error:', error.message, error.stack);
        res.status(500).json({ message: `Server error: ${error.message}` });
    }
});

// Login endpoint
app.post('/login', async (req, res) => {
    const { email, password } = req.body;
    console.log('Login request:', { email, password: '****' });

    if (!email || !password) {
        console.log('Missing fields');
        return res.status(400).json({ message: 'Email and password are required' });
    }

    try {
        const connection = await pool.getConnection();
        const [rows] = await connection.query('SELECT id, username, email, password FROM users WHERE email = ?', [email]);

        if (rows.length === 0) {
            console.log('User not found:', email);
            connection.release();
            return res.status(401).json({ message: 'Invalid email or password' });
        }

        const user = rows[0];
        const isMatch = await bcrypt.compare(password, user.password);

        if (!isMatch) {
            console.log('Invalid password for:', email);
            connection.release();
            return res.status(401).json({ message: 'Invalid email or password' });
        }

        const token = jwt.sign(
            { id: user.id, email: user.email },
            process.env.SECRET_KEY,
            { expiresIn: '1h' }
        );
        console.log('Token generated for:', email);

        connection.release();
        res.status(200).json({ message: 'Login successful', token });
    } catch (error) {
        console.error('Login error:', error.message, error.stack);
        res.status(500).json({ message: `Server error: ${error.message}` });
    }
});

// Forgot password endpoint
app.post('/forgot-password', async (req, res) => {
    const { email } = req.body;
    console.log('Forgot password request:', { email });

    if (!email) {
        console.log('Email not provided');
        return res.status(400).json({ message: 'Email is required' });
    }

    if (!emailRegex.test(email)) {
        console.log('Invalid email:', email);
        return res.status(400).json({ message: 'Invalid email address' });
    }

    try {
        const connection = await pool.getConnection();
        const [rows] = await connection.query('SELECT id FROM users WHERE email = ?', [email]);

        if (rows.length === 0) {
            console.log('Email not found:', email);
            connection.release();
            return res.status(404).json({ message: 'Email not found' });
        }

        const token = crypto.randomBytes(32).toString('hex');
        const expiresAt = new Date(Date.now() + 15 * 60 * 1000);
        console.log('Reset token generated:', { email, token });

        await connection.query(
            'INSERT INTO password_resets (email, token, expires_at) VALUES (?, ?, ?)',
            [email, token, expiresAt]
        );

        connection.release();
        res.status(200).json({ message: 'Reset token generated successfully.', token });
    } catch (error) {
        console.error('Forgot password error:', error.message, error.stack);
        res.status(500).json({ message: `Server error: ${error.message}` });
    }
});

// Reset password endpoint
app.post('/reset-password', async (req, res) => {
    const { email, token, newPassword, confirmPassword } = req.body;
    console.log('Reset password request:', { email, token: '****', newPassword: '****', confirmPassword: '****' });

    if (!email || !token || !newPassword || !confirmPassword) {
        console.log('Missing fields');
        return res.status(400).json({ message: 'All fields are required' });
    }

    if (newPassword !== confirmPassword) {
        console.log('Passwords do not match');
        return res.status(400).json({ message: 'Passwords do not match' });
    }

    if (newPassword.length < 8) {
        console.log('Password too short');
        return res.status(400).json({ message: 'Password must be at least 8 characters long' });
    }

    try {
        const connection = await pool.getConnection();
        const [rows] = await connection.query(
            'SELECT id, expires_at FROM password_resets WHERE email = ? AND token = ?',
            [email, token]
        );

        if (rows.length === 0) {
            console.log('Invalid token for:', email);
            connection.release();
            return res.status(400).json({ message: 'Invalid or expired token' });
        }

        const resetRecord = rows[0];
        if (new Date() > new Date(resetRecord.expires_at)) {
            console.log('Token expired for:', email);
            connection.release();
            return res.status(400).json({ message: 'Token has expired' });
        }

        const hashedPassword = await bcrypt.hash(newPassword, 10);
        console.log('Password hashed for reset:', email);

        await connection.query(
            'UPDATE users SET password = ? WHERE email = ?',
            [hashedPassword, email]
        );

        await connection.query(
            'DELETE FROM password_resets WHERE email = ? AND token = ?',
            [email, token]
        );
        console.log('Password reset and token deleted:', email);

        connection.release();
        res.status(200).json({ message: 'Password reset successful' });
    } catch (error) {
        console.error('Reset password error:', error.message, error.stack);
        res.status(500).json({ message: `Server error: ${error.message}` });
    }
});

// Start server
app.listen(port, () => {
    console.log(`Server running at http://localhost:${port}`);
});