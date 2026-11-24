# Database backup, migration, and recovery

Use the MySQL command-line client and `mysqldump`. Replace the host, port, user, and database below with the values from `.env`. MySQL prompts for the password; do not put it in the command or commit it.

## Before a schema or application update

Stop the Flask app, then create a full database backup before running `python init_db.py`:

```powershell
New-Item -ItemType Directory -Force .\backups
mysqldump --host=127.0.0.1 --port=3306 --user=your_mysql_user --password --single-transaction --routines --triggers --events --add-drop-database --databases ltsm_db --result-file=.\backups\ltsm-before-change.sql
```

Confirm that the backup file exists and is non-empty. Keep it outside source control; the repository ignores the `backups/` directory. Store another copy somewhere protected if the database is important.

## If a migration fails

1. Stop the app and keep the error output. Do not run `python init_db.py --reset`; it drops the project tables and is not a rollback.
2. If the initializer reports an error, fix the cause and rerun `python init_db.py`. Its schema updates are additive and designed to be rerun.
3. If the update left the database unusable or changed data incorrectly, restore the pre-update backup below. MySQL can implicitly commit DDL statements, so `connection.rollback()` alone cannot undo a schema migration.

## Restore a backup

**This replaces the entire named database with the contents of the dump.** Verify that the host and database name are correct and stop the app before restoring. Use a MySQL account with permission to drop and recreate the database.

In PowerShell, run the import through Command Prompt because `<` is Command Prompt input-redirection syntax:

```powershell
cmd.exe /c "mysql --host=127.0.0.1 --port=3306 --user=your_mysql_user --password < .\backups\ltsm-before-change.sql"
```

For Command Prompt or a Unix shell, the import command is:

```text
mysql --host=127.0.0.1 --port=3306 --user=your_mysql_user --password < backups/ltsm-before-change.sql
```

After restoring, start the app and verify sign-in and the affected workflow before allowing users back in.
