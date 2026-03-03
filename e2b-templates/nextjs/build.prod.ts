import { Template, defaultBuildLogger } from 'e2b'
import { template } from './template'

async function main() {
  await Template.build(template, 'nextjs-sandbox', {
    onBuildLogs: defaultBuildLogger(),
    cpuCount: 4,      // 4 CPU cores
    memoryMb: 4096,   // 4 GB RAM
  });
}

main().catch(console.error);