import { cp, access } from "node:fs/promises";
import { existsSync } from "node:fs";
import { fileURLToPath, pathToFileURL } from "node:url";
import path from "node:path";

const root = fileURLToPath(new URL("../", import.meta.url));
const output = path.join(root, ".next", "standalone");
await access(path.join(output, "server.js"));
await cp(path.join(root, ".next", "static"), path.join(output, ".next", "static"), { recursive: true, force: true });
if (existsSync(path.join(root, "public"))) await cp(path.join(root, "public"), path.join(output, "public"), { recursive: true, force: true });
process.env.PORT ||= "3180";
process.env.HOSTNAME ||= "127.0.0.1";
await import(pathToFileURL(path.join(output, "server.js")).href);
