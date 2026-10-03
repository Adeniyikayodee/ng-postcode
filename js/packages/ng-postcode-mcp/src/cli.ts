#!/usr/bin/env node
/** `npx ng-postcode-mcp`: serves over stdio, so nothing else may print to stdout. */

import { serveStdio } from "@modelcontextprotocol/server/stdio";
import { createServer, settingsFromEnv } from "./server.js";

const settings = settingsFromEnv(process.env);
if (typeof settings === "string") {
  console.error(`ng-postcode-mcp: ${settings}`);
  process.exit(1);
}
serveStdio(() => createServer(settings));
