// OSM search via Drover's cached, rate-limited proxy endpoint

const SEARCH_DEBOUNCE_MS = 400;
const MIN_QUERY_LENGTH = 3;
const searchTimers = new WeakMap();

function search(query, format, limit, resultsContainer, type) {
  const trimmed = (query || '').trim();
  if (trimmed.length < MIN_QUERY_LENGTH) {
    $(resultsContainer).empty().removeClass('show');
    return;
  }
  const params = new URLSearchParams({
    q: trimmed,
    limit: String(limit || 5),
  });
  fetch(`/location-search/?${params.toString()}`, {
    credentials: 'same-origin',
  })
    .then((response) => (response.ok ? response.json() : []))
    .then((locations) => {
      renderDropdown(Array.isArray(locations) ? locations : [], resultsContainer, type);
    })
    .catch(() => {
      $(resultsContainer).empty().removeClass('show');
    });
}

function renderDropdown(locations, resultsContainer, type) {
  const $container = $(resultsContainer);
  $container.empty();
  if (!Array.isArray(locations) || !locations.length) {
    $container.removeClass('show');
    return;
  }
  locations.forEach((element) => {
    const $item = $('<a>')
      .addClass(`dropdown-item location-item ${type}-venue`)
      .attr('href', '#')
      .attr('data-latitude', element.lat)
      .attr('data-longitude', element.lon)
      .attr('data-display-name', element.display_name)
      .text(element.display_name);
    $container.append($item);
  });
  if (locations[0].licence) {
    const $licence = $('<div>')
      .addClass('copyright-location-results small')
      .text(locations[0].licence);
    $container.append($licence);
  }
  $container.addClass('show');
}

function scheduleSearch(inputElement, type) {
  clearTimeout(searchTimers.get(inputElement));
  const timer = setTimeout(() => {
    const $input = $(inputElement);
    search(
      $input.val(),
      'json',
      5,
      $input.parent().find('.location-results'),
      type
    );
  }, SEARCH_DEBOUNCE_MS);
  searchTimers.set(inputElement, timer);
}

$(document).ready(function () {
  $('#venue').on('input keyup', function () {
    scheduleSearch(this, 'group');
  });

  $(document).on('input keyup', '#event_venue_address', function () {
    scheduleSearch(this, 'event');
  });

  $(document).on('click', '.location-item', function (event) {
    event.preventDefault();
    const displayName = $(this).attr('data-display-name') || '';
    const longitude = $(this).attr('data-longitude') || '';
    const latitude = $(this).attr('data-latitude') || '';
    if ($(this).hasClass('group-venue')) {
      $('#venue').val(displayName);
    } else if ($(this).hasClass('event-venue')) {
      $('#event_venue_address').val(displayName);
      const params = new URLSearchParams({ lon: longitude, lat: latitude });
      const mapLink = `${window.location.protocol}//${window.location.host}/mapview/?${params.toString()}`;
      $('#event_venue_map').val(mapLink);
    }
    $(this).closest('.location-results').empty().removeClass('show');
  });
});