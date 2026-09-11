"""PQ discovery and argument refusal through the real MCP transport, without CAD."""
import asyncio
import json
import sys
from pathlib import Path

import pytest


def test_pq_operation_discovery_and_refusal(tmp_path):
    pytest.importorskip('mcp')
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    root = Path(__file__).resolve().parents[2]

    async def check():
        server = StdioServerParameters(command=sys.executable,
            args=[str(root/'tools/cadagent_mcp.py'), '--serve'])
        async with stdio_client(server) as (reader, writer):
            async with ClientSession(reader, writer) as session:
                await session.initialize()
                response = await session.call_tool('cad.registry_explain', {'op_id':'pq_label.class.set'})
                data = json.loads(response.content[0].text)
                assert data['result']['record']['args_schema']['required'] == ['handles','class_id','class_kind']
                response = await session.call_tool('cad.run_operation', {
                    'op_id':'pq_label.class.set', 'out':str(tmp_path), 'args':{'layer':'A-WALL'}})
                data = json.loads(response.content[0].text)['result']
                assert data['executed'] is False
                assert 'INVALID_OPERATION_ARGUMENTS' in data['reason']
    asyncio.run(check())
