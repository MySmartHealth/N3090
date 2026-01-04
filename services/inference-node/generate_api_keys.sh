#!/bin/bash
# Generate secure API keys for production deployment

echo "Generating secure API keys..."
echo ""

echo "# Production API Keys - Generated $(date)" > .api_keys.env
echo "# KEEP SECURE - DO NOT COMMIT TO GIT" >> .api_keys.env
echo "" >> .api_keys.env

# Generate keys for each model
for model in "tiny-llama-1b-8080" "bimedix2-8081" "medicine-llm-8082" "tiny-llama-1b-8083" "openinsurance-8084" "biomistral-8085"; do
    key=$(openssl rand -hex 32)
    echo "API_KEY_${model^^}=$key" >> .api_keys.env
    echo "✅ Generated key for $model"
done

echo ""
echo "✅ API keys saved to .api_keys.env"
echo "⚠️  Remember to add .api_keys.env to .gitignore"

# Add to .gitignore if not already there
if ! grep -q ".api_keys.env" .gitignore 2>/dev/null; then
    echo ".api_keys.env" >> .gitignore
    echo "✅ Added .api_keys.env to .gitignore"
fi

cat .api_keys.env
