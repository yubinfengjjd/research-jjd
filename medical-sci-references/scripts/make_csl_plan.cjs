// Render with an explicitly supplied, locally installed citeproc-js and CSL style.
// No network, package installation, document UI, or guessed bibliography strings.
const fs = require('node:fs');
const vm = require('node:vm');
const crypto = require('node:crypto');
const [inputPath, processorPath, stylePath, localePath, outputPath] = process.argv.slice(2);
if (!outputPath) throw new Error('Usage: node make_csl_plan.cjs INPUT PROCESSOR STYLE LOCALE OUTPUT');
if (fs.existsSync(outputPath)) throw new Error('Output already exists');
const sha = p => crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const data = JSON.parse(fs.readFileSync(inputPath, 'utf8'));
const context = vm.createContext({console});
vm.runInContext(fs.readFileSync(processorPath, 'utf8'), context, {timeout: 10000});
if (!context.CSL || !context.CSL.Engine) throw new Error('Supplied processor exposes no CSL.Engine');
const locale = fs.readFileSync(localePath, 'utf8');
const engine = new context.CSL.Engine({
  retrieveLocale: () => locale,
  retrieveItem: id => {
    if (!Object.hasOwn(data.items, String(id))) throw new Error('Unknown item ' + id);
    return JSON.parse(JSON.stringify(data.items[String(id)]));
  }
}, fs.readFileSync(stylePath, 'utf8'), 'en-US');
engine.setOutputFormat('html');
const previous = [], rendered = [];
for (const original of data.citations) {
  const citation = JSON.parse(JSON.stringify(original));
  citation.properties = {noteIndex: citation.properties?.noteIndex || 0};
  const result = engine.processCitationCluster(citation, previous, []);
  for (const [index, text] of result[1]) rendered[index] = text;
  previous.push([citation.citationID, citation.properties.noteIndex]);
}
const bibliography = engine.makeBibliography();
if (!bibliography || rendered.length !== data.citations.length || rendered.some(x => !x)) {
  throw new Error('Incomplete CSL output');
}
const output = {
  schema: 1, source_sha256: data.source_sha256,
  resources: Object.fromEntries([['input',inputPath], ['processor',processorPath], ['style',stylePath], ['locale',localePath]]
    .map(([name,path]) => [name,{path,sha256:sha(path)}])),
  processor_version: context.CSL.PROCESSOR_VERSION,
  citations: data.citations.map((c,i) => ({citationID:c.citationID,
    item_ids:c.citationItems.map(x=>String(x.id)), html:rendered[i]})),
  bibliography: bibliography[1].map((html,i) => ({item_ids:bibliography[0].entry_ids[i].map(String),html}))
};
fs.writeFileSync(outputPath, JSON.stringify(output,null,2)+'\n', {encoding:'utf8',flag:'wx'});
console.log(JSON.stringify({citations:output.citations.length,bibliography:output.bibliography.length}));
