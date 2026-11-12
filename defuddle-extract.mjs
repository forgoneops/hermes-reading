import { readFileSync } from 'node:fs'
import { parseHTML } from 'linkedom'
import { Defuddle } from 'defuddle/node'

const url = process.argv[2]
if (!url) throw new Error('URL argument is required')
const html = readFileSync(0, 'utf8')
const { document } = parseHTML(html)
const result = await Defuddle(document, url, { markdown: true })
const text = String(result.content ?? '')
  .replace(/^!\[[^\]]*\]\([^)]*\)\s*$/gm, '')
  .replace(/!\[[^\]]*\]\([^)]*\)/g, '')
  .replace(/\n{3,}/g, '\n\n')
  .trim()
process.stdout.write(JSON.stringify({
  title: String(result.title ?? '').trim(),
  text,
  author: result.author || null,
  published: result.published || null,
  site: result.site || null,
}))
