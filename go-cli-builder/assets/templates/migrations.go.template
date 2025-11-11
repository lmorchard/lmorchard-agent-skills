package database

import (
	"fmt"
)

// getMigrations returns all available migrations
// Add new migrations here with incrementing version numbers
func getMigrations() map[int]string {
	return map[int]string{
		// Example migration:
		// 2: `
		// 	CREATE TABLE IF NOT EXISTS settings (
		// 		key TEXT PRIMARY KEY,
		// 		value TEXT NOT NULL,
		// 		updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
		// 	);
		// `,
		// Add your migrations here starting from version 2
		// (version 1 is the initial schema in schema.sql)
	}
}

// RunMigrations executes all pending migrations
func (db *DB) RunMigrations() error {
	// Ensure schema_migrations table exists (created by InitSchema)
	initialized, err := db.IsInitialized()
	if err != nil {
		return fmt.Errorf("failed to check initialization: %w", err)
	}

	if !initialized {
		return fmt.Errorf("database not initialized")
	}

	// Get current version
	currentVersion, err := db.GetMigrationVersion()
	if err != nil {
		return fmt.Errorf("failed to get current version: %w", err)
	}

	// Get all migrations
	migrations := getMigrations()

	// Find maximum version
	maxVersion := currentVersion
	for version := range migrations {
		if version > maxVersion {
			maxVersion = version
		}
	}

	// Apply pending migrations in order
	appliedCount := 0
	for version := currentVersion + 1; version <= maxVersion; version++ {
		migrationSQL, exists := migrations[version]
		if !exists {
			return fmt.Errorf("missing migration for version %d", version)
		}

		if err := db.ApplyMigration(version, migrationSQL); err != nil {
			return fmt.Errorf("failed to apply migration %d: %w", version, err)
		}

		appliedCount++
	}

	if appliedCount > 0 {
		fmt.Printf("Applied %d migration(s), current version: %d\n", appliedCount, maxVersion)
	}

	return nil
}
