import { useEffect } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { useParams } from 'react-router-dom';

import { DATA_FETCH_INTERVAL } from '../helpers/constants';

import { useCustomDatetime, useWindEnabled, useSolarEnabled, useFeatureToggle } from './router';
import { useCurrentZoneHistory } from './redux';

export function useConditionalZoneHistoryFetch() {
  const { zoneId } = useParams();
  const historyData = useCurrentZoneHistory();
  const customDatetime = useCustomDatetime();
  const features = useFeatureToggle();
  const selectedTimeAggregate = useSelector((state) => state.application.selectedTimeAggregate);
  const dispatch = useDispatch();

  // Fetch zone history data only if it's not there yet (and custom timestamp is not used).
  useEffect(() => {
    if (customDatetime) {
      console.error("Can't fetch history when a custom date is provided!");
    } else if (zoneId && Array.isArray(historyData) && historyData.length === 0) {
      console.error('No history data available right now!');
    }
    let hasCorrectTimeAggregate = true;
    if (features.includes('history')) {
      hasCorrectTimeAggregate = historyData && historyData[0]?.aggregation === selectedTimeAggregate;
    }
    const hasDetailedHistory = historyData !== null && historyData[0] && historyData[0]?.hasDetailedData !== false;
    if (zoneId && (!hasDetailedHistory || !hasCorrectTimeAggregate)) {
      dispatch({ type: 'ZONE_HISTORY_FETCH_REQUESTED', payload: { zoneId, features, selectedTimeAggregate } });
    }
  }, [zoneId, historyData, customDatetime, dispatch, features, selectedTimeAggregate]);
}

export function useGridDataPolling() {
  const datetime = useCustomDatetime();
  const features = useFeatureToggle();
  const selectedTimeAggregate = useSelector((state) => state.application.selectedTimeAggregate);
  const dispatch = useDispatch();

  // After initial request, do the polling only if the custom datetime is not specified.
  useEffect(() => {
    let pollInterval;
    dispatch({ type: 'GRID_DATA_FETCH_REQUESTED', payload: { datetime, features, selectedTimeAggregate } });
    if (!datetime) {
      pollInterval = setInterval(() => {
        dispatch({ type: 'GRID_DATA_FETCH_REQUESTED', payload: { datetime, features, selectedTimeAggregate } });
      }, DATA_FETCH_INTERVAL);
    }
    return () => clearInterval(pollInterval);
  }, [datetime, dispatch, features, selectedTimeAggregate]);
}

export function useConditionalWindDataPolling() {
  const windEnabled = useWindEnabled();
  const customDatetime = useCustomDatetime();
  const dispatch = useDispatch();

  // After initial request, do the polling only if the custom datetime is not specified.
  useEffect(() => {
    let pollInterval;
    if (windEnabled) {
      if (customDatetime) {
        dispatch({ type: 'WIND_DATA_FETCH_REQUESTED', payload: { datetime: customDatetime } });
      } else {
        dispatch({ type: 'WIND_DATA_FETCH_REQUESTED' });
        pollInterval = setInterval(() => {
          dispatch({ type: 'WIND_DATA_FETCH_REQUESTED' });
        }, DATA_FETCH_INTERVAL);
      }
    } else {
      // TODO: Find a nicer way to invalidate the wind data (or remove it altogether when wind layer is moved to React).
      dispatch({ type: 'WIND_DATA_FETCH_SUCCEEDED', payload: null });
    }
    return () => clearInterval(pollInterval);
  }, [windEnabled, customDatetime, dispatch]);
}

export function useConditionalSolarDataPolling() {
  const solarEnabled = useSolarEnabled();
  const customDatetime = useCustomDatetime();
  const dispatch = useDispatch();

  // After initial request, do the polling only if the custom datetime is not specified.
  useEffect(() => {
    let pollInterval;
    if (solarEnabled) {
      if (customDatetime) {
        dispatch({ type: 'SOLAR_DATA_FETCH_REQUESTED', payload: { datetime: customDatetime } });
      } else {
        dispatch({ type: 'SOLAR_DATA_FETCH_REQUESTED' });
        pollInterval = setInterval(() => {
          dispatch({ type: 'SOLAR_DATA_FETCH_REQUESTED' });
        }, DATA_FETCH_INTERVAL);
      }
    } else {
      // TODO: Find a nicer way to invalidate the solar data (or remove it altogether when solar layer is moved to React).
      dispatch({ type: 'SOLAR_DATA_FETCH_SUCCEEDED', payload: null });
    }
    return () => clearInterval(pollInterval);
  }, [solarEnabled, customDatetime, dispatch]);
}
