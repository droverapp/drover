$(document).ready(function() {
    console.log("here")
    $('input[name="message-image"').on('change', function() {
        console.log(this.files)
        if (this.files && this.files[0]) {
            var reader = new FileReader();

            reader.onload = function (e) {
                $('#uploaded-image')
                    .attr('src', e.target.result)
                    .width(100);
            };

            reader.readAsDataURL(this.files[0]);
        }
    })
})