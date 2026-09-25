const BASE = 'https://fantasy.premierleague.com/api';
const headers = { 'user-agent': 'Fantasy Edge IQ beta analyzer', 'accept': 'application/json' };

async function getJson(path) {
  const res = await fetch(BASE + path, { headers });
  if (!res.ok) throw new Error(`${path} returned ${res.status}`);
  return await res.json();
}

function num(v, d = null) {
  const n = Number(v);
  return Number.isFinite(n) ? n : d;
}

function price(e) {
  return num(e.now_cost, 0) / 10;
}

function posName(t) {
  return ({ 1: 'GKP', 2: 'DEF', 3: 'MID', 4: 'FWD' })[t] || String(t);
}

function currentEvent(events) {
  return (
    events.find(e => e.is_current)?.id ||
    events.find(e => e.is_next)?.id ||
    events.filter(e => e.finished).slice(-1)[0]?.id ||
    1
  );
}

async function getPicks(teamId, preferredEvent, events) {
  const start = preferredEvent || currentEvent(events);
  const tries = [];

  for (let e = start; e >= Math.max(1, start - 5); e--) {
    tries.push(e);
  }

  for (const e of tries) {
    try {
      return {
        event: e,
        picks: await getJson(`/entry/${teamId}/event/${e}/picks/`)
      };
    } catch (err) {}
  }

  throw new Error('Could not load public picks for this team ID');
}

function nextFixtures(teamId, fixtures, teams, n = 5) {
  return fixtures
    .filter(f => !f.finished && (f.team_h === teamId || f.team_a === teamId))
    .sort((a, b) => String(a.kickoff_time || '').localeCompare(String(b.kickoff_time || '')))
    .slice(0, n)
    .map(f => {
      const home = f.team_h === teamId;
      const oppId = home ? f.team_a : f.team_h;
      const opp = teams.find(t => t.id === oppId)?.short_name || String(oppId);
      const diff = home ? f.team_h_difficulty : f.team_a_difficulty;

      return {
        opp,
        ha: home ? 'H' : 'A',
        difficulty: num(diff, 3)
      };
    });
}

function reliability(e) {
  const minutes = num(e.minutes, 0);
  const starts = num(e.starts, 0);
  const selected = num(e.selected_by_percent, 0);

  const minutesScore = Math.min(55, minutes / 9);
  const startsScore = Math.min(25, starts * 5);
  const ownershipScore = Math.min(20, selected / 2);

  return Math.round(minutesScore + startsScore + ownershipScore);
}

function enrich(e, maps, fixtures) {
  const team = maps.teams.get(e.team) || {};
  const nf = nextFixtures(e.team, fixtures, [...maps.teams.values()], 5);
  const fdr = nf.length ? nf.reduce((s, x) => s + x.difficulty, 0) / nf.length : 3;

  let base = num(e.ep_next, null);

  if (base === null || base <= 0) base = num(e.form, 0);
  if (base <= 0) base = num(e.points_per_game, 0);

  let projection = base + (3 - fdr) * 0.35;

  if (e.status !== 'a') {
    projection *= ((num(e.chance_of_playing_next_round, 0) || 0) / 100);
  }

  projection = Math.max(0, projection);

  const p = price(e);

  return {
    id: e.id,
    web_name: e.web_name,
    full_name: `${e.first_name || ''} ${e.second_name || ''}`.trim(),
    team_short: team.short_name || '',
    team_name: team.name || '',
    pos: posName(e.element_type),
    element_type: e.element_type,
    price: p,
    form: num(e.form, 0),
    ep_next: num(e.ep_next, 0),
    points_per_game: num(e.points_per_game, 0),
    total_points: num(e.total_points, 0),
    selected_by_percent: num(e.selected_by_percent, 0),
    transfers_in_event: num(e.transfers_in_event, 0),
    transfers_out_event: num(e.transfers_out_event, 0),
    status: e.status,
    news: e.news || '',
    chance_next: e.chance_of_playing_next_round,
    minutes: num(e.minutes, 0),
    starts: num(e.starts, 0),
    reliability: reliability(e),
    fdr_next5: Math.round(fdr * 100) / 100,
    next5: nf.map(x => `${x.opp}(${x.ha},${x.difficulty})`).join(' · '),
    projection: Math.round(projection * 10) / 10,
    value: p ? projection / p : 0
  };
}

function reasonSell(p) {
  const r = [];

  if (p.status !== 'a' || p.news) r.push('injury/news risk');
  if (p.fdr_next5 >= 3.6) r.push('hard fixture run');
  if (p.projection < 3.5) r.push('low projection');
  if (p.reliability < 35) r.push('low minutes/security');
  if (p.price >= 7.5 && p.value < 0.55) r.push('weak value for price');

  if (!r.length) r.push('lower projection than available alternatives');

  return r.join(', ');
}

function sellPressure(p) {
  let s = Math.max(0, 7 - p.projection) * 7;

  if (p.status !== 'a' || p.news) s += 30;
  if (p.fdr_next5 >= 3.6) s += 10;
  if (p.reliability < 35) s += 12;
  if (p.price >= 7.5 && p.value < 0.55) s += 10;

  s += Math.min(8, (p.transfers_out_event || 0) / 100000);

  return Math.round(s);
}

function buyReasons(out, cand, priceDiff) {
  const r = [];

  if (cand.projection >= out.projection + 1.5) r.push('higher projection');
  if (cand.fdr_next5 <= out.fdr_next5 - 0.35) r.push('better fixtures');
  if (cand.reliability >= out.reliability + 15) r.push('stronger minutes/security');
  if (cand.form >= out.form + 1.5) r.push('better form');
  if (priceDiff < -0.2) r.push('frees budget');

  if (!r.length) r.push('better overall model score');

  return r;
}

module.exports = async (req, res) => {
  try {
    const teamId = String(req.query.teamId || '').trim();

    if (!/^\d+$/.test(teamId)) {
      return res.status(400).json({
        ok: false,
        error: 'Invalid FPL Team ID'
      });
    }

    const [bootstrap, fixtures, entry] = await Promise.all([
      getJson('/bootstrap-static/'),
      getJson('/fixtures/'),
      getJson(`/entry/${teamId}/`)
    ]);

    const preferred = req.query.event ? Number(req.query.event) : currentEvent(bootstrap.events);
    const { event, picks } = await getPicks(teamId, preferred, bootstrap.events);

    const teamMap = new Map(bootstrap.teams.map(t => [t.id, t]));
    const maps = { teams: teamMap };

    const enriched = bootstrap.elements.map(e => enrich(e, maps, fixtures));
    const byId = new Map(enriched.map(p => [p.id, p]));

    const selectedIds = new Set((picks.picks || []).map(p => p.element));

    const squad = (picks.picks || [])
      .map(pk => ({
        ...byId.get(pk.element),
        pick_position: pk.position,
        multiplier: pk.multiplier
      }))
      .filter(p => p.id);

    const starting = squad.filter(p => (p.multiplier || 0) > 0 || (p.pick_position || 99) <= 11);

    const endpointBank =
      picks.entry_history && Number.isFinite(Number(picks.entry_history.bank))
        ? Number(picks.entry_history.bank) / 10
        : 0;

    const bank = Number.isFinite(Number(req.query.bank))
      ? Math.max(0, Number(req.query.bank))
      : endpointBank;

    const style = String(req.query.style || 'balanced');

    const sells = squad
      .map(p => ({
        player: p,
        sellPressure: sellPressure(p),
        reason: reasonSell(p)
      }))
      .sort((a, b) => b.sellPressure - a.sellPressure)
      .slice(0, 4);

    const ideas = [];

    for (const s of sells) {
      const out = s.player;

      for (const cand of enriched) {
        if (selectedIds.has(cand.id)) continue;
        if (cand.element_type !== out.element_type) continue;
        if (cand.status !== 'a') continue;

        if (cand.reliability < 25 && cand.projection < 4.5) continue;

        const priceDiff = Math.round((cand.price - out.price) * 10) / 10;
        const bankAfter = Math.round((bank - priceDiff) * 10) / 10;

        if (bankAfter < -0.001) continue;

        const gain = Math.round((cand.projection - out.projection) * 10) / 10;

        if (gain <= 0.3) continue;

        let rank =
          gain * 11 +
          cand.projection * 1.5 +
          cand.value * 2 +
          (3 - cand.fdr_next5) * 2 +
          cand.reliability * 0.035;

        if (style === 'safe') rank += cand.reliability * 0.08;
        if (style === 'aggressive') rank += cand.form * 0.65;

        ideas.push({
          out,
          in: cand,
          gain,
          priceDiff,
          bankAfter,
          reasons: buyReasons(out, cand, priceDiff),
          rank
        });
      }
    }

    ideas.sort((a, b) => b.rank - a.rank);

    const captaincy = starting
      .slice()
      .sort((a, b) => b.projection - a.projection)
      .slice(0, 5);

    const warnings = [];

    const injuryFlags = squad.filter(p => p.status !== 'a' || p.news).length;
    const hardFixturePlayers = squad.filter(p => p.fdr_next5 >= 3.6).length;
    const lowSecurityPlayers = squad.filter(p => p.reliability < 35).length;

    if (injuryFlags) warnings.push(`${injuryFlags} player(s) have injury/news flags`);
    if (hardFixturePlayers) warnings.push(`${hardFixturePlayers} player(s) have difficult next-five fixtures`);
    if (lowSecurityPlayers) warnings.push(`${lowSecurityPlayers} player(s) have low minutes/security`);

    const startingProjection = starting.reduce(
      (sum, p) => sum + p.projection * (p.multiplier || 1),
      0
    );

    res.setHeader('Cache-Control', 's-maxage=300, stale-while-revalidate=600');

    return res.status(200).json({
      ok: true,
      teamId,
      event,
      generated: new Date().toISOString().slice(0, 16).replace('T', ' '),
      manager: {
        name: entry.name,
        player_name: [entry.player_first_name, entry.player_last_name].filter(Boolean).join(' ')
      },
      summary: {
        bank,
        startingProjection: Math.round(startingProjection * 10) / 10,
        injuryFlags,
        hardFixturePlayers,
        lowSecurityPlayers
      },
      squad,
      sellCandidates: sells,
      transferIdeas: ideas.slice(0, 6),
      captaincy,
      warnings
    });
  } catch (err) {
    return res.status(500).json({
      ok: false,
      error: err.message || 'Analyzer failed'
    });
  }
};
