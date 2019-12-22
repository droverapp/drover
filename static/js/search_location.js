// OSM search using Nominatim

function search(query, format, limit, results_container, type) {
  const params = `format=${format}&limit=${limit}`;
  const url = `https://nominatim.openstreetmap.org/search/${query}?${params}`;
  fetch(url)
    .then(response => response.json())
      .then(locations => {
        console.log(locations);
        renderDropdown(locations, results_container, type);
      });
}

function renderDropdown(locations, results_container, type) {
  console.log(results_container);
  let dropdown_results = '';
  locations.forEach(element => {
    dropdown_results += `<a data-latitude=${element.lat} data-longitude=${element.lon}
      data-display-name="${element.display_name}"
      class="dropdown-item location-item ${type}-venue" href="#">${element.display_name}</a>`;
  });
  $(results_container).html(dropdown_results);
  if (locations.length) {
    $(results_container).append(`<div class="copyright-location-results">${locations[0].licence}</small>`)
  }
}

$(document).ready(function() {
  $('#venue').on('keyup', function() {
    const query = $(this).val();
    console.log(query);
    search(query, 'json', 5, $(this).parent().find('.location-results'), 'event');
  });

  $(document).on('keyup', '#schedule_venue_name', function() {
    const query = $(this).val();
    console.log(query);
    search(query, 'json', 5, $(this).parent().find('.location-results'), 'schedule');
  })

  $(document).on('click', '.location-item', function() {
    console.log('clicked');
    if ($(this).hasClass('event-venue')) {
      $('#venue').val($(this).data('display-name'));
    } else if ($(this).hasClass('schedule-venue')) {
      $('#schedule_venue_name').val($(this).data('display-name').split(',')[0]);
      $('#schedule_venue_address').val($(this).data('display-name'));
      const map_link = `${window.location.protocol}//${window.location.host}/mapview/?lon=${$(this).data('longitude')}&lat=${$(this).data('latitude')}`;
      $('#schedule_venue_map').val(map_link);
    }
  });

});