/* Javascript for StaffGradedAssignmentXBlock. */
function StaffGradedAssignmentXBlock(runtime, element) {
    function xblock($, _) {
        var uploadUrl = runtime.handlerUrl(element, 'upload_assignment');
        var downloadUrl = runtime.handlerUrl(element, 'download_assignment');
        var template = _.template($(element).find("#sga-tmpl").text());

        function render(state) {
            state.downloadUrl = downloadUrl;
            var content = $(element).find("#sga-content").html(template(state));
            $(content).find("#fileupload").fileupload({
                url: uploadUrl,
                add: function(e, data) {
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
    }

    if (require === undefined) { 
        /** 
         * The LMS does not use require.js (although it loads it...) and
         * does not already load jquery.fileupload.  (It looks like it uses
         * jquery.ajaxfileupload instead.  But our XBlock uses 
         * jquery.fileupload.
         */
        function loadjs(url) {
            $("<script>")
                .attr("type", "text/javascript")
                .attr("src", url)
                .appendTo(element);
        }
        loadjs("/static/js/vendor/jQuery-File-Upload/js/jquery.iframe-transport.js");
        loadjs("/static/js/vendor/jQuery-File-Upload/js/jquery.fileupload.js");
        xblock($, _);
    }
    else {
        /**
         * Studio, on the other hand, uses require.js and already knows about
         * jquery.fileupload.
         */
        require(["jquery", "underscore", "jquery.fileupload"], xblock);
    }
}
