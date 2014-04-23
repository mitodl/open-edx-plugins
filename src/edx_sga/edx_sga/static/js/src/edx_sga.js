/* Javascript for StaffGradedAssignmentXBlock. */
function StaffGradedAssignmentXBlock(runtime, element) {
    require(["jquery", "jquery.fileupload"], function($) {
        var uploadUrl = runtime.handlerUrl(element, 'upload_assignment');
        $(element).find("#fileupload").fileupload({
            url: uploadUrl,
            done: function(e, data) {
                $.each(data.files, function(index, file) {
                    $(element).append("p")
                        .text("Successfully uploaded: " + file.name);
                })
            }
        });
    });
}
