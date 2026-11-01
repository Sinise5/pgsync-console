#!/bin/bash
# Migration script — Centralized .env setup
# Run this ONCE after pulling the new env structure

set -e

echo "============================================"
echo "PGSync Production — Env Migration Script"
echo "============================================"
echo ""

# Step 1: Backup old env files
echo "📦 Step 1: Backing up old .env files..."
if [ -f "pgsync-admin/backend/.env" ]; then
    cp pgsync-admin/backend/.env pgsync-admin/backend/.env.backup
    echo "  ✅ pgsync-admin/backend/.env → .env.backup"
fi

if [ -f "search-api/.env" ]; then
    cp search-api/.env search-api/.env.backup
    echo "  ✅ search-api/.env → .env.backup"
fi

if [ -f "laporan/.env" ]; then
    cp laporan/.env laporan/.env.backup
    echo "  ✅ laporan/.env → .env.backup"
fi

if [ -f ".env" ]; then
    cp .env .env.backup.old
    echo "  ✅ .env (root) → .env.backup.old"
fi

echo ""

# Step 2: Choose environment
echo "🌍 Step 2: Choose environment preset"
echo "  1) Development (local)"
echo "  2) Staging"
echo "  3) Production"
echo "  4) Custom (manual)"
echo ""
read -p "Select environment [1-4]: " env_choice

case $env_choice in
    1)
        echo "  ✅ Using .env.development"
        cp .env.development .env
        ;;
    2)
        echo "  ✅ Using .env.staging"
        cp .env.staging .env
        ;;
    3)
        echo "  ✅ Using .env.production"
        cp .env.production .env
        echo "  ⚠️  REMEMBER: Fill secrets in .env before running!"
        ;;
    4)
        echo "  ✅ Using .env.example"
        cp .env.example .env
        echo "  ⚠️  REMEMBER: Fill ALL values in .env before running!"
        ;;
    *)
        echo "  ❌ Invalid choice. Exiting."
        exit 1
        ;;
esac

echo ""

# Step 3: Migrate secrets from old files
echo "🔐 Step 3: Migrate secrets from old .env files..."

if [ -f "pgsync-admin/backend/.env.backup" ]; then
    # Extract ENCRYPTION_KEY from backup
    OLD_ENC_KEY=$(grep "^ENCRYPTION_KEY=" pgsync-admin/backend/.env.backup | cut -d= -f2-)
    if [ -n "$OLD_ENC_KEY" ]; then
        # Update new .env
        if [[ "$OSTYPE" == "darwin"* ]]; then
            sed -i '' "s|^ENCRYPTION_KEY=.*|ENCRYPTION_KEY=$OLD_ENC_KEY|" .env
        else
            sed -i "s|^ENCRYPTION_KEY=.*|ENCRYPTION_KEY=$OLD_ENC_KEY|" .env
        fi
        echo "  ✅ ENCRYPTION_KEY migrated"
    fi
fi

echo ""

# Step 4: Verify
echo "✅ Step 4: Verify new .env file"
echo ""
echo "Contents of .env (first 20 lines):"
echo "-----------------------------------"
head -20 .env
echo "-----------------------------------"
echo ""

# Step 5: Instructions
echo "🚀 Step 5: Next steps"
echo ""
echo "1. Review .env file: nano .env"
echo "2. Fill any missing secrets (PG_PASSWORD, OPENSEARCH_PASSWORD, etc.)"
echo "3. Test services: docker-compose up"
echo "4. If everything works, cleanup old files:"
echo "   rm pgsync-admin/backend/.env"
echo "   rm search-api/.env"
echo "   rm laporan/.env"
echo ""
echo "Rollback if needed:"
echo "   cp pgsync-admin/backend/.env.backup pgsync-admin/backend/.env"
echo "   cp search-api/.env.backup search-api/.env"
echo ""
echo "============================================"
echo "Migration complete! 🎉"
echo "============================================"
