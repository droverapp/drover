console.log("add_event is loaded");
var events = 0;
function getEventView(name) {
  var $eventView = $('#event-view').clone();
  $eventView.attr('id', 'event-view-' + events);
  $eventView.find('.event-display-name').html(name);
  $eventView.removeClass('hidden');
  return $eventView;
}

function appendEventView(name) {
  $('#event-view-container').append(getEventView(name));
}

function onEventSave() {
  events += 1;
  var $actualEventInput = $('#event-form-tmpl').clone();
  $actualEventInput.attr('id', 'event-form-' + events);

  // Add modal information to inputs
  $actualEventInput.find('#event-id-inp').val($('#event_id').val());
  $actualEventInput.find('#event-id-inp').attr('id', 'event-id-inp-' + events);
  $actualEventInput.find('#event-name-inp').val($('#event_name').val());
  $actualEventInput.find('#event-name-inp').attr('id', 'event-name-inp-' + events);
  $actualEventInput.find('#event-time-inp').val($('#event_time').val());
  $actualEventInput.find('#event-time-inp').attr('id', 'event-time-inp-' + events);
  $actualEventInput.find('#event-instructions-inp').val($('#event_instructions').val());
  $actualEventInput.find('#event-instructions-inp').attr('id', 'event-instructions-inp-' + events);
  $actualEventInput.find('#event-venue-name-inp').val($('#event_venue_name').val());
  $actualEventInput.find('#event-venue-name-inp').attr('id', 'event-venue-name-inp-' + events);
  $actualEventInput.find('#event-venue-address-inp').val($('#event_venue_address').val());
  $actualEventInput.find('#event-venue-address-inp').attr('id', 'event-venue-address-inp-' + events);
  $actualEventInput.find('#event-venue-map-inp').val($('#event_venue_map').val());
  $actualEventInput.find('#event-venue-map-inp').attr('id', 'event-venue-map-inp-' + events);
  $('.form-container').append($actualEventInput);
  if ($('#event_id').val() == '0') {
    appendEventView($('#event_name').val());
  }
  $('#event-form-modal').modal('hide');
}

function fillEventFormModal(data) {
  $('#event_id').val(data['event-id']);
  $('#event_name').val(data['event-name']);
  $('#event_time').val(data['event-time']);
  $('#event_venue_name').val(data['event-venue-name']);
  $('#event_venue_address').val(data['event-venue_address']);
  $('#event_venue_map').val(data['event-venue-map']);
  $('#event_instructions').val(data['event-instructions']);
}

function emptyModal(data) {
  $('#event_id').val('0')
  $('#event_name').val('');
  $('#event_time').val('');
  $('#event_venue_name').val('');
  $('#event_venue_address').val('');
  $('#event_venue_map').val('');
  $('#event_instructions').val('');
}

$(document).ready(function() {
  $('#save-event').on('click', onEventSave);
  $('a[data-toggle=modal], button[data-toggle=modal]').on('click', emptyModal);
  $('.edit-event').on('click', function(){
    var data = {
      "event-id": $(this).data('evt-id'),
      "event-name": $(this).data('evt-name'),
      "event-time": $(this).data('evt-time'),
      "event-venue-name": $(this).data('evt-venue-name'),
      "event-venue-address": $(this).data('evt-venue-address'),
      "event-venue-map": $(this).data('evt-venue-map'),
      "event-instructions": $(this).data('evt-instructions'),
    }
    fillEventFormModal(data)
  });
});
