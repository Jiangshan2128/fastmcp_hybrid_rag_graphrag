@echo off
cd /d "%~dp0"

echo 1/3 Cleaning up previous Inspector processes...
taskkill /f /im node.exe 2>nul
taskkill /f /im python.exe 2>nul
timeout /t 1 /nobreak >nul

echo 2/3 Starting MCP Server...
echo.

echo 3/3 Opening MCP Inspector...
npx @modelcontextprotocol/inspector fastmcp run server.py:mcp --no-banner

pause
