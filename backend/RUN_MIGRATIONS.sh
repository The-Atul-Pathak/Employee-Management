#!/bin/bash
# Migration Setup and Execution Script

echo "🔧 Alembic Migration Setup"
echo "=========================="
echo ""

# Check if we're in the right directory
if [ ! -f "alembic.ini" ]; then
    echo "❌ Error: alembic.ini not found. Please run this from the backend directory."
    echo "   cd backend && bash RUN_MIGRATIONS.sh"
    exit 1
fi

echo "✅ Found alembic.ini in current directory"
echo ""

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: python3 not found. Please install Python 3."
    exit 1
fi

echo "✅ Python 3 found: $(python3 --version)"
echo ""

# Check if alembic is installed
if ! python3 -c "import alembic" 2>/dev/null; then
    echo "⚠️  Alembic not installed. Installing now..."
    pip install alembic sqlalchemy
    if [ $? -ne 0 ]; then
        echo "❌ Failed to install alembic. Please install manually:"
        echo "   pip install alembic sqlalchemy"
        exit 1
    fi
fi

echo "✅ Alembic is installed"
echo ""

# Show migration commands
echo "📋 Available Commands:"
echo "====================="
echo ""
echo "1️⃣  Apply initial migration (creates all tables):"
echo "   alembic upgrade head"
echo ""
echo "2️⃣  Check current migration status:"
echo "   alembic current"
echo ""
echo "3️⃣  View all migrations:"
echo "   alembic history"
echo ""
echo "4️⃣  Create new migration after schema changes:"
echo "   alembic revision --autogenerate -m 'describe_your_changes'"
echo ""
echo "5️⃣  Rollback one step:"
echo "   alembic downgrade -1"
echo ""

# Ask if user wants to apply initial migration now
echo "Would you like to apply the initial migration now? (y/n)"
read -r response

if [[ "$response" =~ ^[Yy]$ ]]; then
    echo ""
    echo "🚀 Applying initial migration..."
    alembic upgrade head

    if [ $? -eq 0 ]; then
        echo ""
        echo "✅ Migration completed successfully!"
        echo ""
        echo "Checking migration status..."
        alembic current
    else
        echo ""
        echo "❌ Migration failed. Check the error messages above."
        exit 1
    fi
else
    echo ""
    echo "📝 To apply migrations when ready, run:"
    echo "   alembic upgrade head"
fi

echo ""
echo "📚 For more information, see:"
echo "   - ALEMBIC_QUICKSTART.md (quick reference)"
echo "   - MIGRATION_GUIDE.md (comprehensive guide)"
echo "   - ALEMBIC_SETUP_SUMMARY.md (setup details)"
