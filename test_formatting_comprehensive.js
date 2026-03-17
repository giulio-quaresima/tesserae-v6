import test from 'node:test';
import assert from 'node:assert/strict';
import { formatReference } from './client/src/utils/formatting.js';

const testCases = [
  {
    name: 'Seneca Hercules Oetaeus (her.o)',
    input: 'seneca.her.o.1',
    expected: 'Seneca, Hercules Oetaeus 1'
  },
  {
    name: 'Seneca Hercules Furens (her.f)',
    input: 'sen.her.f.10',
    expected: 'Seneca, Hercules Furens 10'
  },
  {
    name: 'Alcuin Carmina (carm)',
    input: 'alcuin.carm.5',
    expected: 'Alcuin, Carmina 5'
  },
  {
    name: 'Hildebert Carmen In Libros Regum (carm_lib_reg)',
    input: 'hildeb..carm_lib_reg..1.95',
    expected: 'Hildebert of Lavardin, Carmen in libros regum 1.95'
  },
  {
    name: 'Hildebert De Ordine Mundi',
    input: 'hildebert.de_ordine_mundi.1',
    expected: 'Hildebert of Lavardin, De ordine mundi 1'
  },
  {
    name: 'Hildegard Scivias',
    input: 'hildeg.scivias.1.1',
    expected: 'Hildegard of Bingen, Scivias 1.1'
  },
  {
    name: 'Standard Vergil Aeneid',
    input: 'verg.aen.1.1',
    expected: 'Vergil, Aeneid 1.1'
  },
  {
    name: 'Ovid Heroides (Global fallback)',
    input: 'ovid.her.1',
    expected: 'Ovid, Heroides 1'
  },
  {
    name: 'Cicero In Catilinam',
    input: 'cic.catil.1.1',
    expected: 'Cicero, In Catilinam 1.1'
  },
  {
    name: 'Cicero Pro Archia',
    input: 'cic.arch.5',
    expected: 'Cicero, Pro Archia 5'
  },
  {
    name: 'Plautus Amphitruo',
    input: 'plaut.am.1',
    expected: 'Plautus, Amphitruo 1'
  },
  {
    name: 'Vulgate Genesis',
    input: 'vulgate genesis.1.1',
    expected: 'Vulgate, Genesis 1.1'
  },
  {
    name: 'Sallust Bellum Catilinae',
    input: 'sall.cat.5',
    expected: 'Sallust, Bellum Catilinae 5'
  },
  {
    name: 'Ausonius Mosella',
    input: 'aus.mos.1',
    expected: 'Ausonius, Mosella 1'
  },
  {
    name: 'Prudentius Psychomachia',
    input: 'prud.psych.100',
    expected: 'Prudentius, Psychomachia 100'
  },
  {
    name: 'Claudian De Raptu Proserpinae',
    input: 'claud.rapt.2.1',
    expected: 'Claudian, De Raptu Proserpinae 2.1'
  },
  {
    name: 'Jerome In Hieremiam',
    input: 'jerome.in_hier.1.1',
    expected: 'Jerome, In Hieremiam Prophetam 1.1'
  },
  {
    name: 'Anonymous/Smart Fallback (Underscores)',
    input: 'carm_biblioth.5',
    expected: 'Carm Biblioth 5'
  },
  {
    name: 'Augustine De Civitate Dei (Smart Fallback)',
    input: 'augustine.de_civitate_dei.1.1',
    expected: 'Augustine, De Civitate Dei 1.1'
  }
];

test('formatReference formatting comprehensive cases', () => {
  testCases.forEach(tc => {
    const result = formatReference(tc.input);
    assert.strictEqual(
      result,
      tc.expected,
      `Unexpected formatting for case "${tc.name}" with input "${tc.input}"`
    );
  });
});
