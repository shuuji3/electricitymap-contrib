import * as d3 from 'd3-format';
import { TIME } from './constants';
import * as translation from './translation';

const DEFAULT_NUM_DIGITS = 3;

const formatPower = function (d, numDigits = DEFAULT_NUM_DIGITS) {
  // Assume MW input
  if (d == null || isNaN(d)) {
    return d;
  }
  return `${d3.format(`.${numDigits}s`)(d * 1e6)}W`;
};
const formatCo2 = function (d, numDigits = DEFAULT_NUM_DIGITS) {
  let value = d;
  // Assume gCO₂ / h input
  value /= 60; // Convert to gCO₂ / min
  value /= 1e6; // Convert to tCO₂ / min
  if (d == null || isNaN(d)) {
    return d;
  }

  if (d >= 1) {
    // a ton or more
    return `${d3.format(`.${numDigits}s`)(value)}t ${translation.translate('ofCO2eqPerMinute')}`;
  } else {
    return `${d3.format(`.${numDigits}s`)(value * 1e6)}g ${translation.translate('ofCO2eqPerMinute')}`;
  }
};
const scalePower = function (maxPower) {
  // Assume MW input
  if (maxPower < 1) {
    return {
      unit: 'kW',
      formattingFactor: 1e-3,
    };
  }
  if (maxPower < 1e3) {
    return {
      unit: 'MW',
      formattingFactor: 1,
    };
  } else {
    return {
      unit: 'GW',
      formattingFactor: 1e3,
    };
  }
};

const formatDate = function (date, lang, time) {
  if (!date || !time) {
    return '';
  }

  switch (time) {
    case TIME.HOURLY:
      return new Intl.DateTimeFormat(lang, { dateStyle: 'long', timeStyle: 'short' }).format(date);
    case TIME.DAILY:
      return new Intl.DateTimeFormat(lang, { dateStyle: 'long' }).format(date);
    case TIME.MONTHLY:
      return new Intl.DateTimeFormat(lang, { dateStyle: 'long' }).format(date);
    case TIME.YEARLY:
      return new Intl.DateTimeFormat(lang, { dateStyle: 'long' }).format(date);
    default:
      console.error(`${time} is not implemented`);
      return '';
  }
};

const getLocaleUnit = (dateUnit, lang) =>
  new Intl.NumberFormat(lang, {
    style: 'unit',
    unit: dateUnit,
    unitDisplay: 'long',
  })
    .formatToParts(1)
    .filter((x) => x.type === 'unit')[0].value;

const getLocaleNumberFormat = (lang, { unit, unitDisplay, range }) =>
  new Intl.NumberFormat(lang, {
    style: 'unit',
    unit,
    unitDisplay: unitDisplay || 'long',
  }).format(range);

const formatTimeRange = (lang, timeAggregate) => {
  // Note that not all browsers fully support all languages
  switch (timeAggregate) {
    case TIME.HOURLY:
      return getLocaleNumberFormat(lang, { unit: 'hour', range: 24 });
    case TIME.DAILY:
      return getLocaleUnit('month', lang);
    case TIME.MONTHLY:
      return getLocaleUnit('year', lang);
    case TIME.YEARLY:
      return getLocaleNumberFormat(lang, { unit: 'year', range: 5 });
    default:
      console.error(`${timeAggregate} is not implemented`);
      return '';
  }
};

const formatDateTick = function (date, lang, timeAggregate) {
  if (!date || !timeAggregate) {
    return '';
  }

  switch (timeAggregate) {
    case TIME.HOURLY:
      return new Intl.DateTimeFormat(lang, { timeStyle: 'short' }).format(date);
    case TIME.DAILY:
      return new Intl.DateTimeFormat(lang, { month: 'long', day: 'numeric' }).format(date);
    case TIME.MONTHLY:
      return new Intl.DateTimeFormat(lang, { month: 'short' }).format(date);
    case TIME.YEARLY:
      return new Intl.DateTimeFormat(lang, { year: 'numeric' }).format(date);
    default:
      console.error(`${timeAggregate} is not implemented`);
      return '';
  }
};

export { formatPower, formatCo2, scalePower, formatDate, formatTimeRange, formatDateTick };
