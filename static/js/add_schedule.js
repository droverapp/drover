console.log("add_schedule is loaded");
var schedules = 0;
function getScheduleView(name) {
  var $scheduleView = $('#schedule-view').clone();
  $scheduleView.attr('id', 'schedule-view-' + schedules);
  $scheduleView.find('.schedule-display-name').html(name);
  $scheduleView.removeClass('hidden');
  return $scheduleView;
}

function appendScheduleView(name) {
  $('#schedule-view-container').append(getScheduleView(name));
}

function onScheduleSave() {
  schedules += 1;
  var $actualScheduleInput = $('#schedule-form-tmpl').clone();
  $actualScheduleInput.attr('id', 'schedule-form-' + schedules);

  // Add modal information to inputs$actualScheduleInput.find('#schedule-name-inp').val($('#schedule_name').val());
  $actualScheduleInput.find('#schedule-id-inp').val($('#schedule_id').val());
  $actualScheduleInput.find('#schedule-id-inp').attr('id', 'schedule-id-inp-' + schedules);
  $actualScheduleInput.find('#schedule-name-inp').val($('#schedule_name').val());
  $actualScheduleInput.find('#schedule-name-inp').attr('id', 'schedule-name-inp-' + schedules);
  $actualScheduleInput.find('#schedule-time-inp').val($('#schedule_time').val());
  $actualScheduleInput.find('#schedule-time-inp').attr('id', 'schedule-time-inp-' + schedules);
  $actualScheduleInput.find('#schedule-instructions-inp').val($('#schedule_instructions').val());
  $actualScheduleInput.find('#schedule-instructions-inp').attr('id', 'schedule-instructions-inp-' + schedules);
  $actualScheduleInput.find('#schedule-venue-name-inp').val($('#schedule_venue_name').val());
  $actualScheduleInput.find('#schedule-venue-name-inp').attr('id', 'schedule-venue-name-inp-' + schedules);
  $actualScheduleInput.find('#schedule-venue-address-inp').val($('#schedule_venue_address').val());
  $actualScheduleInput.find('#schedule-venue-address-inp').attr('id', 'schedule-venue-address-inp-' + schedules);
  $actualScheduleInput.find('#schedule-venue-map-inp').val($('#schedule_venue_map').val());
  $actualScheduleInput.find('#schedule-venue-map-inp').attr('id', 'schedule-venue-map-inp-' + schedules);
  $('.form-container').append($actualScheduleInput);
  if ($('#schedule_id').val() == '0') {
    appendScheduleView($('#schedule_name').val());
  }
  $('#schedule-form-modal').modal('hide');
}

function fillScheduleFormModal(data) {
  $('#schedule_id').val(data['schedule-id']);
  $('#schedule_name').val(data['schedule-name']);
  $('#schedule_time').val(data['schedule-time']);
  $('#schedule_venue_name').val(data['schedule-venue-name']);
  $('#schedule_venue_address').val(data['schedule-venue_address']);
  $('#schedule_venue_map').val(data['schedule-venue-map']);
  $('#schedule_instructions').val(data['schedule-instructions']);
}

function emptyModal(data) {
  $('#schedule_id').val('0')
  $('#schedule_name').val('');
  $('#schedule_time').val('');
  $('#schedule_venue_name').val('');
  $('#schedule_venue_address').val('');
  $('#schedule_venue_map').val('');
  $('#schedule_instructions').val('');
}

$(document).ready(function() {
  $('#save-schedule').on('click', onScheduleSave);
  $('a[data-toggle=modal], button[data-toggle=modal]').on('click', emptyModal);
  $('.edit-schedule').on('click', function(){
    var data = {
      "schedule-id": $(this).data('sch-id'),
      "schedule-name": $(this).data('sch-name'),
      "schedule-time": $(this).data('sch-time'),
      "schedule-venue-name": $(this).data('sch-venue-name'),
      "schedule-venue-address": $(this).data('sch-venue-address'),
      "schedule-venue-map": $(this).data('sch-venue-map'),
      "schedule-instructions": $(this).data('sch-instructions'),
    }
    fillScheduleFormModal(data)
  });
});