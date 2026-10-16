// Calcul astronomique de secours (île Maurice) : lever et coucher du soleil et de la lune, phases de la Lune.
// Sert quand Météo Maurice n'a pas (encore) publié la période ; écart avec les valeurs publiées : 1 min au plus.
// Soleil : Meeus, « Astronomical Algorithms », chap. 25. Lune : Montenbruck et Pfleger, « MiniMoon », et
// principaux termes de distance de Meeus, chap. 47. Phases : Meeus, chap. 49.
(function (root) {
  "use strict";
  const RAD = Math.PI / 180, ARCS = 206264.806, DAY = 864e5, MU = 4 * 3600e3;
  // Point de référence et conventions ajustés sur les heures publiées par Météo Maurice :
  // lever/coucher = bord supérieur à 34' sous l'horizon, secondes tronquées ; phases arrondies à la minute.
  const LAT = -20.1 * RAD, LON = 57.57;
  const DT = 69 / 86400; // ΔT = TT − UT (≈ 69 s dans les années 2020)

  const frac = x => x - Math.floor(x);
  const jd = ms => ms / DAY + 2440587.5;
  const { sin, cos, asin, atan2 } = Math;

  // Soleil : ascension droite et déclinaison apparentes (rad)
  function sun(ms) {
    const T = (jd(ms) + DT - 2451545) / 36525;
    const M = (357.52911 + 35999.05029 * T) * RAD;
    const C = (1.914602 - 0.004817 * T) * sin(M) + (0.019993 - 0.000101 * T) * sin(2 * M) + 0.000289 * sin(3 * M);
    const om = (125.04 - 1934.136 * T) * RAD;
    const lam = (280.46646 + 36000.76983 * T + C - 0.00569 - 0.00478 * sin(om)) * RAD;
    const eps = (23.439291 - 0.0130042 * T + 0.00256 * cos(om)) * RAD;
    return { ra: atan2(cos(eps) * sin(lam), cos(lam)), dec: asin(sin(eps) * sin(lam)) };
  }

  // Lune : ascension droite et déclinaison (rad, équinoxe de la date), distance (km)
  function moon(ms) {
    const T = (jd(ms) + DT - 2451545) / 36525, P = 2 * Math.PI;
    const L0 = frac(0.606433 + 1336.855225 * T);
    const l = P * frac(0.374897 + 1325.552410 * T);   // anomalie moyenne de la Lune
    const ls = P * frac(0.993133 + 99.997361 * T);    // anomalie moyenne du Soleil
    const D = P * frac(0.827361 + 1236.853086 * T);   // élongation moyenne
    const F = P * frac(0.259086 + 1342.227825 * T);   // argument de latitude
    const dL = 22640 * sin(l) - 4586 * sin(l - 2 * D) + 2370 * sin(2 * D) + 769 * sin(2 * l) - 668 * sin(ls)
      - 412 * sin(2 * F) - 212 * sin(2 * l - 2 * D) - 206 * sin(l + ls - 2 * D) + 192 * sin(l + 2 * D)
      - 165 * sin(ls - 2 * D) - 125 * sin(D) - 110 * sin(l + ls) + 148 * sin(l - ls) - 55 * sin(2 * F - 2 * D);
    const S = F + (dL + 412 * sin(2 * F) + 541 * sin(ls)) / ARCS, h = F - 2 * D;
    const N = -526 * sin(h) + 44 * sin(l + h) - 31 * sin(-l + h) - 23 * sin(ls + h) + 11 * sin(-ls + h)
      - 25 * sin(-2 * l + F) + 21 * sin(-l + F);
    const lam = P * frac(L0 + dL / 1296e3), bet = (18520 * sin(S) + N) / ARCS;
    const dist = 385000.56 - 20905.355 * cos(l) - 3699.111 * cos(2 * D - l) - 2955.968 * cos(2 * D)
      - 569.925 * cos(2 * l) + 246.158 * cos(2 * D - 2 * l) - 204.586 * cos(2 * D - ls) - 170.733 * cos(2 * D + l)
      - 152.138 * cos(2 * D - ls - l) - 129.620 * cos(ls - l) + 108.743 * cos(D) + 104.755 * cos(ls + l);
    const eps = (23.439291 - 0.0130042 * T) * RAD;
    const x = cos(bet) * cos(lam), y = cos(bet) * sin(lam), z = sin(bet);
    return { ra: atan2(y * cos(eps) - z * sin(eps), x), dec: asin(y * sin(eps) + z * cos(eps)), dist };
  }

  // Hauteur géocentrique (rad) d'un astre à l'instant ms
  function altitude(p, ms) {
    const d = jd(ms) - 2451545, T = d / 36525;
    const H = (280.46061837 + 360.98564736629 * d + 0.000387933 * T * T + LON) * RAD - p.ra;
    return asin(sin(LAT) * sin(p.dec) + cos(LAT) * cos(p.dec) * cos(H));
  }

  // Hauteur du bord supérieur, réfraction de 34' comprise : positive quand l'astre est levé
  const HORIZON = {
    sun: ms => altitude(sun(ms), ms) + (16 + 34) / 60 * RAD,
    moon: ms => {
      const p = moon(ms), h = altitude(p, ms);
      return h - asin(6378.14 / p.dist) * cos(h) + asin(1737.4 / p.dist) + 34 / 60 * RAD;
    },
  };

  const pad = n => String(n).padStart(2, "0");
  const hhmm = ms => { const x = new Date(ms + MU); return `${pad(x.getUTCHours())}:${pad(x.getUTCMinutes())}`; };

  // Lever et coucher d'un jour (heure de Maurice) : "HH:MM" ou null si l'évènement n'a pas lieu ce jour-là
  function riseSet(body, y, m, d) {
    const f = HORIZON[body], start = Date.UTC(y, m - 1, d) - MU, out = { rise: null, set: null };
    let t0 = start, f0 = f(t0);
    for (let k = 1; k <= 144; k++) { // pas de 10 min, puis dichotomie à la seconde
      const t1 = start + k * 6e5, f1 = f(t1);
      const key = f0 <= 0 && f1 > 0 ? "rise" : f0 > 0 && f1 <= 0 ? "set" : null;
      if (key && !out[key]) {
        let a = t0, b = t1;
        for (let i = 0; i < 10; i++) { const c = (a + b) / 2; if ((f(c) > 0) === (f1 > 0)) b = c; else a = c; }
        out[key] = hhmm((a + b) / 2);
      }
      t0 = t1; f0 = f1;
    }
    return out;
  }

  // Phases (Meeus, chap. 49) : [{t: instant ms arrondi à la minute, code: "NM"|"FQ"|"FM"|"LQ"}] entre deux instants
  // [coefficient, puissance de E, multiple de M', multiple de M, multiple de F, multiple de Ω]
  const CORR = {
    NM: [[-0.40720, 0, 1, 0, 0, 0], [0.17241, 1, 0, 1, 0, 0], [0.01608, 0, 2, 0, 0, 0], [0.01039, 0, 0, 0, 2, 0],
      [0.00739, 1, 1, -1, 0, 0], [-0.00514, 1, 1, 1, 0, 0], [0.00208, 2, 0, 2, 0, 0], [-0.00111, 0, 1, 0, -2, 0],
      [-0.00057, 0, 1, 0, 2, 0], [0.00056, 1, 2, 1, 0, 0], [-0.00042, 0, 3, 0, 0, 0], [0.00042, 1, 0, 1, 2, 0],
      [0.00038, 1, 0, 1, -2, 0], [-0.00024, 1, 2, -1, 0, 0], [-0.00017, 0, 0, 0, 0, 1], [-0.00007, 0, 1, 2, 0, 0],
      [0.00004, 0, 2, 0, -2, 0], [0.00004, 0, 0, 3, 0, 0], [0.00003, 0, 1, 1, -2, 0], [0.00003, 0, 2, 0, 2, 0],
      [-0.00003, 0, 1, 1, 2, 0], [0.00003, 0, 1, -1, 2, 0], [-0.00002, 0, 1, -1, -2, 0], [-0.00002, 0, 3, 1, 0, 0],
      [0.00002, 0, 4, 0, 0, 0]],
    FM: [[-0.40614, 0, 1, 0, 0, 0], [0.17302, 1, 0, 1, 0, 0], [0.01614, 0, 2, 0, 0, 0], [0.01043, 0, 0, 0, 2, 0],
      [0.00734, 1, 1, -1, 0, 0], [-0.00515, 1, 1, 1, 0, 0], [0.00209, 2, 0, 2, 0, 0], [-0.00111, 0, 1, 0, -2, 0],
      [-0.00057, 0, 1, 0, 2, 0], [0.00056, 1, 2, 1, 0, 0], [-0.00042, 0, 3, 0, 0, 0], [0.00042, 1, 0, 1, 2, 0],
      [0.00038, 1, 0, 1, -2, 0], [-0.00024, 1, 2, -1, 0, 0], [-0.00017, 0, 0, 0, 0, 1], [-0.00007, 0, 1, 2, 0, 0],
      [0.00004, 0, 2, 0, -2, 0], [0.00004, 0, 0, 3, 0, 0], [0.00003, 0, 1, 1, -2, 0], [0.00003, 0, 2, 0, 2, 0],
      [-0.00003, 0, 1, 1, 2, 0], [0.00003, 0, 1, -1, 2, 0], [-0.00002, 0, 1, -1, -2, 0], [-0.00002, 0, 3, 1, 0, 0],
      [0.00002, 0, 4, 0, 0, 0]],
    Q: [[-0.62801, 0, 1, 0, 0, 0], [0.17172, 1, 0, 1, 0, 0], [-0.01183, 1, 1, 1, 0, 0], [0.00862, 0, 2, 0, 0, 0],
      [0.00804, 0, 0, 0, 2, 0], [0.00454, 1, 1, -1, 0, 0], [0.00204, 2, 0, 2, 0, 0], [-0.00180, 0, 1, 0, -2, 0],
      [-0.00070, 0, 1, 0, 2, 0], [-0.00040, 0, 3, 0, 0, 0], [-0.00034, 1, 2, -1, 0, 0], [0.00032, 1, 0, 1, 2, 0],
      [0.00032, 1, 0, 1, -2, 0], [-0.00028, 2, 1, 2, 0, 0], [0.00027, 1, 2, 1, 0, 0], [-0.00017, 0, 0, 0, 0, 1],
      [-0.00005, 0, 1, -1, -2, 0], [0.00004, 0, 2, 0, 2, 0], [-0.00004, 0, 1, 1, 2, 0], [0.00004, 0, 1, -2, 0, 0],
      [0.00003, 0, 1, 1, -2, 0], [0.00003, 0, 0, 3, 0, 0], [0.00002, 0, 2, 0, -2, 0], [0.00002, 0, 1, -1, 2, 0],
      [-0.00002, 0, 3, 1, 0, 0]],
  };
  const PLANETS = [[299.77, 0.107408, 0.000325], [251.88, 0.016321, 0.000165], [251.83, 26.651886, 0.000164],
    [349.42, 36.412478, 0.000126], [84.66, 18.206239, 0.000110], [141.74, 53.303771, 0.000062],
    [207.14, 2.453732, 0.000060], [154.84, 7.306860, 0.000056], [34.52, 27.261239, 0.000047],
    [207.19, 0.121824, 0.000042], [291.34, 1.844379, 0.000040], [161.72, 24.198154, 0.000037],
    [239.56, 25.513099, 0.000035], [331.55, 3.592518, 0.000023]];
  const CODES = ["NM", "FQ", "FM", "LQ"];

  function phaseAt(k) {
    const T = k / 1236.85, q = Math.round((k - Math.floor(k)) * 4) % 4, code = CODES[q];
    let jde = 2451550.09766 + 29.530588861 * k + 0.00015437 * T * T - 0.00000015 * T ** 3 + 0.00000000073 * T ** 4;
    const E = 1 - 0.002516 * T - 0.0000074 * T * T;
    const M = (2.5534 + 29.1053567 * k - 0.0000014 * T * T) * RAD;
    const Mp = (201.5643 + 385.81693528 * k + 0.0107582 * T * T + 0.00001238 * T ** 3) * RAD;
    const F = (160.7108 + 390.67050284 * k - 0.0016118 * T * T - 0.00000227 * T ** 3) * RAD;
    const Om = (124.7746 - 1.56375588 * k + 0.0020672 * T * T) * RAD;
    for (const [c, e, mp, mm, f, om] of CORR[code === "FQ" || code === "LQ" ? "Q" : code])
      jde += c * E ** e * sin(mp * Mp + mm * M + f * F + om * Om);
    if (code === "FQ" || code === "LQ") {
      const W = 0.00306 - 0.00038 * E * cos(M) + 0.00026 * cos(Mp) - 0.00002 * cos(Mp - M) + 0.00002 * cos(Mp + M) + 0.00002 * cos(2 * F);
      jde += code === "FQ" ? W : -W;
    }
    PLANETS.forEach(([a, b, c], i) => { jde += c * sin((a + b * k - (i ? 0 : 0.009173 * T * T)) * RAD); });
    return { t: Math.round(((jde - DT) - 2440587.5) * DAY / 6e4) * 6e4, code };
  }

  function phases(from, to) {
    const out = [];
    for (let k = Math.floor((jd(from) - 2451550.09766) / 29.530588861) - 1; ; k += 0.25) {
      const p = phaseAt(k);
      if (p.t > to) return out;
      if (p.t >= from) out.push(p);
    }
  }

  const Astro = { riseSet, phases };
  if (typeof module !== "undefined" && module.exports) module.exports = Astro;
  else root.Astro = Astro;
})(this);
