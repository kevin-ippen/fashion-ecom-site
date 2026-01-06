#!/bin/bash
# Check progress of image copy operation

SOURCE_COUNT=44441
DEST_PATH="dbfs:/Volumes/main/fashion_sota/product_images"

echo "============================================"
echo "Image Copy Progress Monitor"
echo "============================================"
echo ""
echo "Source: /Volumes/main/fashion_demo/raw_data/images"
echo "Destination: /Volumes/main/fashion_sota/product_images"
echo "Total files to copy: $SOURCE_COUNT"
echo ""

# Check if copy process is running
if ps aux | grep -q "[d]atabricks fs cp.*fashion_demo.*fashion_sota"; then
    echo "✅ Copy process is RUNNING"
    echo ""
else
    echo "⚠️  Copy process is NOT running"
    echo ""
fi

# Count copied files
echo "Counting copied files..."
COPIED=$(databricks fs ls "$DEST_PATH" --profile work 2>/dev/null | wc -l)

# Calculate progress
PERCENT=$(echo "scale=2; ($COPIED / $SOURCE_COUNT) * 100" | bc)

echo ""
echo "📊 Progress:"
echo "   Copied: $COPIED / $SOURCE_COUNT files"
echo "   Progress: ${PERCENT}%"
echo ""

# Estimate time remaining (rough)
if [ "$COPIED" -gt 0 ]; then
    # This is very rough and assumes linear copy speed
    echo "⏱️  Copy in progress... check again in a few minutes"
else
    echo "⏳ Copy starting..."
fi

echo ""
echo "============================================"
echo "To check progress again, run:"
echo "  ./check_copy_progress.sh"
echo "============================================"
