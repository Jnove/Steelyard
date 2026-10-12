// Refresh the standalone prototype from the checked-in engine snapshots.
const fs = require('node:fs');
const path = require('node:path');
const fixture = require('../frontend/src/mocks/fixtures/data.json');
const snapshot = {
  fixture_id: fixture.fixture_id,
  project: fixture.projects[0],
  evaluation: fixture.evaluation.results,
  schemes: fixture.schemes.filter(s => !s.parent_id),
  roles: Object.fromEntries(Object.entries(fixture.ranks).map(([key, rank]) => [key, {
    label: rank.weights_used.role_name,
    weights: rank.weights_used.weights,
    ranking: rank.ranking,
    excluded: rank.excluded,
  }])),
};
const target = path.join(__dirname, 'prototype', 'comparison-data.js');
fs.writeFileSync(target, 'window.COMPARISON_DATA = ' + JSON.stringify(snapshot, null, 2) + ';\n');
console.log('Updated design/prototype/comparison-data.js from checked-in fixtures.');
