import { mkdirSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import {
  BANKS_RESOURCE_ID,
  BRANCHES_RESOURCE_ID,
  findBranch,
  isClosed,
  loadBanks,
  loadBranches,
  mapUrl,
  nearestBranches,
  searchBranches,
  shortBankName,
  toBank,
  toBranch,
} from '../../israel-bank-branches/index.js'

const [fixturesPath, datasetDir] = process.argv.slice(2)

const snake = (name) => name.replace(/([a-z0-9])([A-Z])/g, '$1_$2').toLowerCase()
const snakeKeys = (value) => {
  if (Array.isArray(value)) return value.map(snakeKeys)
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.entries(value).map(([name, item]) => [snake(name), snakeKeys(item)]))
  }
  return value
}

const raw = {}
const capturing = async (url, init) => {
  const response = await fetch(url, init)
  const text = await response.text()
  const resource = new URL(url).searchParams.get('resource_id')
  raw[resource] = JSON.parse(text)
  return new Response(text, { status: response.status, headers: response.headers })
}

const retrievedAt = new Date().toISOString()
const branches = await loadBranches({ fetch: capturing, timeoutMs: 60000 })
const banks = await loadBanks({ fetch: capturing, timeoutMs: 60000 })
const branchRecords = raw[BRANCHES_RESOURCE_ID].result.records
const bankRecords = raw[BANKS_RESOURCE_ID].result.records

let seed = 20261126
const random = () => {
  seed = (seed + 0x6d2b79f5) | 0
  let t = seed
  t = Math.imul(t ^ (t >>> 15), t | 1)
  t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
  return ((t ^ (t >>> 14)) >>> 0) / 4294967296
}
const pick = (list) => list[Math.floor(random() * list.length)]
const between = (low, high) => low + Math.floor(random() * (high - low + 1))

const syntheticBranchRecords = [
  { Bank_Code: 12, Bank_Name: 'בנק הפועלים בע"מ', Branch_Code: 532, Branch_Name: '  שאול   המלך ', Branch_Address: 'דניאל פריש 3 ללא', City: 'תל אביב -יפו*', Zip_Code: 6473104, POB: null, Telephone: '03-6935769', Handicap_Access: 'כן', day_closed: 'יום ו', Branch_Type: 'רגיל', Open_Date: '1/1/1949', Close_Date: '', Merge_Bank: null, Merge_Branch: null, X_Coordinate: 32.074431, Y_Coordinate: 34.782914 },
  { Bank_Code: '10', Bank_Name: 'בנק לאומי לישראל בע"מ ', Branch_Code: '861', Branch_Name: 'בת ים', Branch_Address: 'בלפור 80 0', City: 'בת ים', Zip_Code: '', POB: '1234', Telephone: 3, Handicap_Access: 'לא', day_closed: 'יום ש', Open_Date: '14/05/2020', Close_Date: '01/02/2024', Merge_Bank: '', Merge_Branch: 900, X_Coordinate: '', Y_Coordinate: null },
  { Bank_Code: 20, Branch_Code: 1, Handicap_Access: 'אולי', day_closed: 'שבת', Open_Date: '2020-01-01', Merge_Bank: 31, Merge_Branch: 0, X_Coordinate: '0', Y_Coordinate: ' ' },

]

const syntheticBankRecords = [
  ...['www.bank.co.il', 'https://Bank.CO.IL/path?x=1', 'http://example.com', 'bank', '', 'www.bank.co.il/he', 'HTTPS://WWW.EXAMPLE.ORG', 'ftp.example.com', 'example.c', 'a b.co.il', 'www.bank.co.il:8080/x']
    .map((Internet_Address, index) => ({ Bank_Code: 90 + index, Bank_Name: 'בנק בדיקה בע"מ', Category: ' בנק ', Internet_Address, Swift_Code: ' abcdilit ', Address: 'רחוב  1', City: 'עיר', Telephone: '*1234' })),
  ...Array.from({ length: 200 }, (_, index) => ({
    Bank_Code: pick([index, String(index), ` ${index} `]),
    Bank_Name: `${pick(['בנק', 'בנק  ', ' '])}${pick(['א', 'ב', 'מסד'])}${pick([' בע"מ', 'בע"מ', ' בע"מ ', '', ' בעמ'])}`,
    Category: pick(['בנקים רגילים', ' בנק  חוץ ', '', null]),
    Internet_Address: `${pick(['', 'http://', 'https://', 'HTTP://', 'ftp://'])}${pick(['www.', '', 'WWW.'])}${pick(['bank', 'b-1', 'בנק', 'a b'])}${pick(['.co.il', '.com', '.c', '', '.CO.IL', '.org:8443', '.co.il:443'])}${pick(['', '/', '/he', '/he?x=1', '#top', '/a b'])}`,
    Swift_Code: pick(['poalilit', ' LUMIILITXXX ', '', null]),
    Address: pick(['רחוב  1', null, '  ']),
    City: pick(['תל אביב -יפו', 'ירושלים  ', null]),
    Telephone: pick(['03-1234567', 31234567, null]),
  })),
]

const tokensOf = (branch) => `${branch.city} ${branch.name} ${branch.address}`.split(/\s+/).filter((word) => word.length > 1)

const queries = [
  'בת ים', 'תל אביב', 'ירושלים', 'חיפה', 'הרצל', 'רוטשילד', "ג'ורג'", 'גורג', 'קרית', 'קריית', 'ראשון', 'באר שבע', 'ב"ש', '', '   ', 'xyz', 'TEL', '12', 'מרכז', 'שאול המלך',
  ...Array.from({ length: 140 }, () => {
    const words = tokensOf(pick(branches))
    const word = pick(words.length ? words : ['א'])
    return random() < 0.5 ? word.slice(0, between(1, word.length)) : `${word} ${pick([...tokensOf(pick(branches)), 'ב'])}`
  }),
]
const searchOptions = [{}, { includeClosed: true }, { limit: 5 }, { bankCode: 12 }, { bankCode: '10', includeClosed: true, limit: 100 }, { bankCode: 999 }]

const pythonSearch = (options) =>
  Object.fromEntries(Object.entries(options).map(([name, value]) => [snake(name), value]))

const branchKeys = (list) => list.map((branch) => [branch.bankCode, branch.code, branch.closedOn])

const searchCases = queries.flatMap((query, index) => {
  const options = searchOptions[index % searchOptions.length]
  return [{ query, kwargs: pythonSearch(options), result: branchKeys(searchBranches(branches, query, options)) }]
})
for (const query of ['תל אביב', 'רמת גן', 'נתניה', 'א', 'ב', 'מ', 'רחוב', 'שד']) {
  for (const options of searchOptions) {
    searchCases.push({ query, kwargs: pythonSearch(options), result: branchKeys(searchBranches(branches, query, options)) })
  }
}

const findCases = [
  ...Array.from({ length: 200 }, () => {
    const branch = pick(branches)
    return [branch.bankCode, branch.code]
  }),
  ...Array.from({ length: 50 }, () => [pick([4, 9, 10, 11, 12, 13, 14, 17, 20, 31, 34, 46, 52, 54, 99]), between(1, 999)]),
  ['12', '532'],
  [12, 1],
].map(([bankCode, code]) => {
  const found = findBranch(branches, bankCode, code)
  return { args: [bankCode, code], result: found ? snakeKeys(found) : null }
})

const nearestCases = [
  [32.0167, 34.75, {}],
  [32.0853, 34.7818, { limit: 10 }],
  [31.7683, 35.2137, { bankCode: 12 }],
  ...Array.from({ length: 220 }, () => [29.5 + random() * 3.8, 34.25 + random() * 1.65, pick([{}, { limit: between(1, 20) }, { bankCode: pick([10, 11, 12, 20, 31]) }])]),
].map(([latitude, longitude, options]) => ({
  args: [latitude, longitude],
  kwargs: pythonSearch(options),
  result: nearestBranches(branches, latitude, longitude, options).map((branch) => [branch.bankCode, branch.code, branch.distanceKm]),
}))

const fixtures = {
  branch_records: [...branchRecords, ...syntheticBranchRecords].map((record) => ({ record, branch: snakeKeys(toBranch(record)) })),
  bank_records: [...bankRecords, ...syntheticBankRecords].map((record) => ({ record, bank: snakeKeys(toBank(record)) })),
  short_bank_name: [...bankRecords.map((record) => record.Bank_Name), ...branchRecords.map((record) => record.Bank_Name), 'בנק  דיסקונט   בע"מ  ', 'בע"מ', '', null].map((name) => [name, shortBankName(name ?? '')]),
  is_closed: branches.map(isClosed),
  map_url: branches.map(mapUrl),
  find: findCases,
  search: searchCases,
  nearest: nearestCases,
}

writeFileSync(fixturesPath, `${JSON.stringify(fixtures)}\n`)

const flatBranch = (branch) => {
  const { mergedInto, ...rest } = branch
  return snakeKeys({ ...rest, mergedIntoBankCode: mergedInto?.bankCode ?? null, mergedIntoCode: mergedInto?.code ?? null })
}

const csvCell = (value) => {
  if (value === null || value === undefined) return ''
  const text = String(value)
  return /[",\n\r]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text
}

const writeTable = (name, rows) => {
  const columns = Object.keys(rows[0])
  writeFileSync(join(datasetDir, `${name}.csv`), `﻿${[columns.join(','), ...rows.map((row) => columns.map((column) => csvCell(row[column])).join(','))].join('\n')}\n`)
  writeFileSync(join(datasetDir, `${name}.jsonl`), `${rows.map((row) => JSON.stringify(row)).join('\n')}\n`)
  return columns
}

mkdirSync(datasetDir, { recursive: true })
const sortedBranches = [...branches].sort((a, b) => a.bankCode - b.bankCode || a.code - b.code || a.closedOn.localeCompare(b.closedOn))
const branchColumns = writeTable('branches', sortedBranches.map(flatBranch))
const bankColumns = writeTable('banks', [...banks].sort((a, b) => a.code - b.code).map(snakeKeys))

console.log(JSON.stringify({
  retrievedAt,
  branchRecords: branchRecords.length,
  bankRecords: bankRecords.length,
  branches: branches.length,
  openBranches: branches.filter((branch) => !isClosed(branch)).length,
  banks: banks.length,
  branchColumns,
  bankColumns,
  fixtureCounts: { branch_records: fixtures.branch_records.length, bank_records: fixtures.bank_records.length, find: findCases.length, search: searchCases.length, nearest: nearestCases.length },
}))
