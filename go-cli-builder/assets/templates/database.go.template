package database

import (
	"database/sql"
	_ "embed"
	"fmt"
	"os"
	"path/filepath"

	_ "github.com/mattn/go-sqlite3"
)

//go:embed schema.sql
var schemaSQL string

// DB wraps a SQLite database connection
type DB struct {
	conn *sql.DB
}

// New creates and initializes a new database connection
func New(dbPath string) (*DB, error) {
	// Ensure directory exists
	dir := filepath.Dir(dbPath)
	if dir != "." && dir != "/" {
		if err := os.MkdirAll(dir, 0755); err != nil {
			return nil, fmt.Errorf("failed to create database directory: %w", err)
		}
	}

	// Open database connection
	conn, err := sql.Open("sqlite3", fmt.Sprintf("%s?_foreign_keys=ON&_journal_mode=WAL", dbPath))
	if err != nil {
		return nil, fmt.Errorf("failed to open database: %w", err)
	}

	// Set connection pool limits (SQLite works best with limited concurrency)
	conn.SetMaxOpenConns(1)
	conn.SetMaxIdleConns(1)

	db := &DB{conn: conn}

	// Initialize schema and run migrations
	if err := db.InitSchema(); err != nil {
		conn.Close()
		return nil, fmt.Errorf("failed to initialize schema: %w", err)
	}

	if err := db.RunMigrations(); err != nil {
		conn.Close()
		return nil, fmt.Errorf("failed to run migrations: %w", err)
	}

	return db, nil
}

// Close closes the database connection
func (db *DB) Close() error {
	if db.conn != nil {
		return db.conn.Close()
	}
	return nil
}

// InitSchema creates the initial database schema
func (db *DB) InitSchema() error {
	_, err := db.conn.Exec(schemaSQL)
	if err != nil {
		return fmt.Errorf("failed to execute schema: %w", err)
	}
	return nil
}

// IsInitialized checks if the database has been initialized
func (db *DB) IsInitialized() (bool, error) {
	// Check if schema_migrations table exists
	var count int
	err := db.conn.QueryRow(`
		SELECT COUNT(*)
		FROM sqlite_master
		WHERE type='table' AND name='schema_migrations'
	`).Scan(&count)

	if err != nil {
		return false, fmt.Errorf("failed to check initialization: %w", err)
	}

	return count > 0, nil
}

// GetMigrationVersion returns the current migration version
func (db *DB) GetMigrationVersion() (int, error) {
	var version int
	err := db.conn.QueryRow("SELECT COALESCE(MAX(version), 0) FROM schema_migrations").Scan(&version)
	if err != nil {
		return 0, fmt.Errorf("failed to get migration version: %w", err)
	}
	return version, nil
}

// ApplyMigration applies a specific migration
func (db *DB) ApplyMigration(version int, sql string) error {
	tx, err := db.conn.Begin()
	if err != nil {
		return fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer func() { _ = tx.Rollback() }()

	// Execute migration SQL
	if _, err := tx.Exec(sql); err != nil {
		return fmt.Errorf("failed to execute migration %d: %w", version, err)
	}

	// Record migration
	if _, err := tx.Exec(
		"INSERT INTO schema_migrations (version) VALUES (?)",
		version,
	); err != nil {
		return fmt.Errorf("failed to record migration %d: %w", version, err)
	}

	if err := tx.Commit(); err != nil {
		return fmt.Errorf("failed to commit migration %d: %w", version, err)
	}

	return nil
}
