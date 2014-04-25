/* Javascript for StaffGradedAssignmentXBlock. */
function StaffGradedAssignmentXBlock(runtime, element) {
    require(["jquery", "underscore", "jquery.fileupload"], function($, _) {
        var uploadUrl = runtime.handlerUrl(element, 'upload_assignment');
        var downloadUrl = runtime.handlerUrl(element, 'download_assignment');
        var template = _.template($(element).find("#sga-tmpl").text());

        function render(state) {
            state.downloadUrl = downloadUrl;
            var content = $(element).find("#sga-content").html(template(state));
            $(content).find("#fileupload").fileupload({
                url: uploadUrl,
                add: function(e, data) {
                    console.log("hey", data);
                    var do_upload = $(content).find("#do-upload")
                        .text("Upload " + data.files[0].name + " ");
                    $('<button/>')
                        .text('Upload now')
                        .appendTo(do_upload)
                        .click(function() {
                            do_upload.text("Uploading...");
                            data.submit();
                        });
                },
                progressall: function(e, data) {
                    var percent = parseInt(data.loaded / data.total * 100, 10);
                    $(content).find("#do-upload").text(
                        "Uploading... " + percent + "%");
                },
                done: function(e, data) { render(data.result); }
            });
        }

        $(function($) { // onLoad
            var state = $(element).find(".sga-block").attr("data-state");
            render(JSON.parse(state));
        });
    });
}
