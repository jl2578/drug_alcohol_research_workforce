import {test, expect} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

// The front pages read the same pinned dataset exports as the explorer.
const pages = [['overview', './'], ['content', 'content.html'], ['funding', 'funding.html'], ['careers', 'careers.html'], ['data', 'data.html']];

async function settled(page) {
  await expect(page.locator('.status')).toHaveCount(0);
  await expect(page.locator('[aria-busy="true"]')).toHaveCount(0);
  await expect(page.locator('.error')).toHaveCount(0);
}

for (const [name, path] of pages) {
  test(`${name} page loads its released numbers without errors`, async ({page}) => {
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
    await page.goto(path);
    await settled(page);
    await expect(page.locator('nav a[aria-current="page"]')).toHaveCount(1);
    expect(errors).toEqual([]);
  });

  for (const width of [1280, 390]) {
    test(`axe WCAG A/AA checks: ${name} page at ${width}px`, async ({page}) => {
      await page.setViewportSize({width, height: 1000});
      await page.goto(path);
      await settled(page);
      const results = await new AxeBuilder({page}).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze();
      expect(results.violations).toEqual([]);
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
      const small = await page.locator('main').evaluate(root => [...root.querySelectorAll('*')]
        .filter(el => el.getClientRects().length && getComputedStyle(el).visibility !== 'hidden' && [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim()))
        .filter(el => parseFloat(getComputedStyle(el).fontSize) < 12).map(el => el.textContent.slice(0, 40)));
      expect(small).toEqual([]);
    });
  }
}

test('overview states the released reach, role and composition counts', async ({page}) => {
  await page.goto('./');
  await settled(page);
  await expect(page.locator('#findings')).toContainText('3,236 of 7,964 research-doctorate works');
  await expect(page.locator('#findings')).toContainText('110 of 190 authors');
  await expect(page.locator('#composition-lead')).toHaveText('Research doctorates make up 60% of the 13,227 works; master’s theses 26%.');
  await page.getByRole('button', {name: 'By field'}).click();
  await expect(page.locator('#composition .row').first()).toContainText('Psychology');
});

test('content comparisons keep the saved paired interval and direction', async ({page}) => {
  await page.goto('content.html');
  await settled(page);
  await expect(page.locator('#content-lead')).toContainText('Cross-sectional observational, 46.7% for Master’s · Psychology vs 32.1% for Research doctorate · Psychology (+14.6 points, 95% CI 8.1 to 21.5)');
  await page.locator('#compare').selectOption('period:Research doctorate|BF01');
  await expect(page.locator('#content-title')).toHaveText('Research doctorate · Psychology: 2017–2023 vs 2010–2016');
  await page.locator('#compare').selectOption('inst:U166027');
  await expect(page.locator('#content-count')).toHaveText('Descriptive comparison: no intervals for the average or the differences.');
  await page.getByRole('button', {name: 'Data type'}).click();
  await expect(page.locator('#content-chart')).toContainText('can add to more than 100%');
});

test('funding page shows reach counts and the log-scale rate ratios', async ({page}) => {
  await page.goto('funding.html');
  await settled(page);
  await expect(page.locator('#reach')).toContainText('40.6% · 3,236 of 7,964');
  await expect(page.locator('#counts')).toContainText('1.155 (1.036 to 1.289)');
  await expect(page.locator('#counts')).toContainText('Master’s ÷ research doctorate');
  await page.getByRole('button', {name: 'Master’s'}).click();
  await expect(page.locator('#connected-lead')).toContainText('For master’s works');
});

test('careers panels keep occupations, roles and destinations separate', async ({page}) => {
  await page.goto('careers.html');
  await settled(page);
  await expect(page.locator('#jobs')).toContainText('19-1042.00');
  await expect(page.locator('#jobs')).toContainText('69 · 36.3%');
  await expect(page.locator('#jobs .stack')).toHaveCount(0);
  await page.locator('#jobs-controls').getByRole('button', {name: 'PsyD'}).click();
  await expect(page.locator('#jobs')).toContainText('An industry split is not released for this degree group.');
  await expect(page.locator('#roles .stack')).toHaveCount(6);
  await expect(page.locator('#roles .tag')).toHaveCount(0);
  await expect(page.locator('#outside')).toContainText('6211, 6213');
  await page.locator('#outside-controls').getByRole('button', {name: 'Research or clinical likelihood'}).click();
  await expect(page.locator('#outside .tag')).toHaveCount(0);
  await expect(page.locator('#outside .stack').first()).toHaveAttribute('aria-label', /^All outside, 120 authors/);
});

test('a failed load offers a working retry', async ({page}) => {
  await page.route('**/dashboard/metadata/index.json', route => route.abort('connectionfailed'));
  await page.goto('./');
  await expect(page.locator('#findings .error')).toContainText('could not be loaded');
  await page.unroute('**/dashboard/metadata/index.json');
  await page.locator('#findings .error button').click();
  await expect(page.locator('#findings')).toContainText('3,236 of 7,964');
});

test('front pages link to the full explorer', async ({page}) => {
  await page.goto('data.html');
  await page.getByRole('link', {name: 'Open the full explorer'}).click();
  await expect(page).toHaveURL(/explore\.html$/);
  await expect(page.locator('#status')).toContainText('Selection loaded');
});
