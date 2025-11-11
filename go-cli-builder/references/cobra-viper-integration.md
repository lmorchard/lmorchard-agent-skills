# Cobra + Viper Integration Pattern

This document explains how Cobra (CLI framework) and Viper (configuration management) are integrated in the generated Go CLI projects.

## Architecture Overview

The integration follows these principles:

1. **Configuration Priority** (highest to lowest):
   - Command-line flags
   - Environment variables
   - Config file values
   - Default values

2. **Lazy Loading**: Configuration is loaded once in `PersistentPreRun`, before any command executes

3. **Centralized Access**: The `GetConfig()` and `GetLogger()` functions in `cmd/root.go` provide access to configuration and logging

## Key Components

### Root Command (`cmd/root.go`)

The root command sets up the entire configuration system:

```go
var rootCmd = &cobra.Command{
    PersistentPreRun: func(cmd *cobra.Command, args []string) {
        initConfig()
        setupLogging()
    },
}
```

### Configuration Initialization (`initConfig()`)

This function:
1. Determines config file location (from flag or default)
2. Sets default values
3. Enables environment variable reading
4. Reads the config file (if it exists)

### Flag Binding

Flags are bound to Viper keys using `viper.BindPFlag()`:

```go
rootCmd.PersistentFlags().StringP("verbose", "v", false, "verbose output")
viper.BindPFlag("verbose", rootCmd.PersistentFlags().Lookup("verbose"))
```

This creates the hierarchy: CLI flag → Viper key → Config struct

## Adding New Configuration

To add a new configuration option:

1. **Add to config struct** (`internal/config/config.go`):
   ```go
   type Config struct {
       MyNewOption string
   }
   ```

2. **Add flag** (`cmd/root.go` or command-specific file):
   ```go
   rootCmd.PersistentFlags().String("my-option", "default", "description")
   viper.BindPFlag("my_option", rootCmd.PersistentFlags().Lookup("my-option"))
   ```

3. **Set default** (`cmd/root.go` in `initConfig()`):
   ```go
   viper.SetDefault("my_option", "default_value")
   ```

4. **Add to config example** (`.yaml.example`):
   ```yaml
   my_option: "default_value"
   ```

5. **Access in commands**:
   ```go
   cfg := GetConfig()
   value := cfg.MyNewOption
   // or directly from viper:
   value := viper.GetString("my_option")
   ```

## Command-Specific Configuration

For configuration specific to a single command:

1. Add the flag to the command's `init()` function, not the root command
2. Use a nested structure in the config struct:
   ```go
   type Config struct {
       Fetch struct {
           Concurrency int
           Timeout     time.Duration
       }
   }
   ```

3. Bind with a namespaced key:
   ```go
   viper.BindPFlag("fetch.concurrency", fetchCmd.Flags().Lookup("concurrency"))
   ```

## Environment Variables

Viper automatically maps environment variables when you call `viper.AutomaticEnv()`.

By default, environment variables are matched by converting the key to uppercase and replacing `.` with `_`:

- Config key: `fetch.concurrency`
- Environment variable: `FETCH_CONCURRENCY`

## Best Practices

1. **Use PersistentFlags for global options**: Options that apply to all commands should be on `rootCmd.PersistentFlags()`

2. **Use command-specific Flags for local options**: Options specific to one command should be on that command's `Flags()`

3. **Provide sensible defaults**: Always set defaults in `initConfig()` so the tool works without a config file

4. **Document in .yaml.example**: Keep the example config file up to date

5. **Keep flag names kebab-case**: Use hyphens in CLI flags (`--my-option`) and underscores in Viper keys (`my_option`)

6. **Use GetConfig() for structured access**: Prefer accessing configuration through the typed Config struct rather than calling viper.Get* directly in commands
