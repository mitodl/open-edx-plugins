/* Javascript for StaffGradedAssignmentXBlock. */
function StaffGradedAssignmentXBlock(runtime, element) {
    function xblock($, _) {
        var uploadUrl = runtime.handlerUrl(element, 'upload_assignment');
        var downloadUrl = runtime.handlerUrl(element, 'download_assignment');
        var annotatedUrl = runtime.handlerUrl(element, 'download_annotated');
        var getStaffGradingUrl = runtime.handlerUrl(element, 'get_staff_grading_data');
        var staffDownloadUrl = runtime.handlerUrl(element, 'staff_download');
        var staffAnnotatedUrl = runtime.handlerUrl(element, 'staff_download_annotated');
        var staffUploadUrl = runtime.handlerUrl(element, 'staff_upload_annotated');
        var enterGradeUrl = runtime.handlerUrl(element, 'enter_grade');
        var removeGradeUrl = runtime.handlerUrl(element, 'remove_grade');
        var template = _.template($(element).find("#sga-tmpl").text());
        var gradingTemplate;

        function render(state) {
            // Add download urls to template context
            state.downloadUrl = downloadUrl;
            state.annotatedUrl = annotatedUrl;
            state.error = state.error ? state.error : false;

            // Render template
            var content = $(element).find("#sga-content").html(template(state));

            // Set up file upload
            $(content).find(".fileupload").fileupload({
                url: uploadUrl,
                add: function(e, data) {
                    var do_upload = $(content).find(".upload").html('');
                    $('<button/>')
                        .text('Upload ' + data.files[0].name)
                        .appendTo(do_upload)
                        .click(function() {
                            do_upload.text("Uploading...");
                            data.submit();
                        });
                },
                progressall: function(e, data) {
                    var percent = parseInt(data.loaded / data.total * 100, 10);
                    $(content).find(".upload").text(
                        "Uploading... " + percent + "%");
                },
                done: function(e, data) { 
                    /* When you try to upload a file that exceeds Django's size
                     * limit for file uploads, Django helpfully returns a 200 OK
                     * response with a JSON payload of the form:
                     * 
                     *   {'success': '<error message'}
                     * 
                     * This is perfectly reasonable.  Unimpeachable even.  Makes
                     * perfect sense.
                     */
                    if (data.result.success !== undefined) {
                        // Actually, this is an error
                        state.error = data.result.success;
                        render(state);
                    }
                    else {
                        render(data.result); 
                    }
                }
            });
        }

        function renderStaffGrading(data) {
            $(".grade-modal").hide();

            // Add download urls to template context
            data.downloadUrl = staffDownloadUrl;
            data.annotatedUrl = staffAnnotatedUrl;

            // Render template
            $(element).find("#grade-info")
                .html(gradingTemplate(data))
                .data(data);

            // Map data to table rows
            data.assignments.map(function(assignment) {
                $(element).find("#grade-info #row-" + assignment.module_id)
                    .data(assignment);
            });

            // Set up grade entry modal
            $(element).find(".enter-grade-button")
                .leanModal({closeButton: "#enter-grade-cancel"})
                .on("click", handleGradeEntry);

            // Set up annotated file upload
            $(element).find("#grade-info .fileupload").each(function() {
                var row = $(this).parents("tr");
                var url = staffUploadUrl + "?module_id=" + row.data("module_id");
                $(this).fileupload({
                    url: url,
                    /*
                    add: function(e, data) {
                        var upload = $(this).parents(".upload").html('');
                        $('<button/>')
                            .text('Upload ' + data.files[0].name)
                            .appendTo(upload)
                            .click(function() {
                                upload.text("Uploading...");
                                data.submit();
                            });
                    },
                    */
                    progressall: function(e, data) {
                        var percent = parseInt(data.loaded / data.total * 100, 10);
                        row.find(".upload").text("Uploading... " + percent + "%");
                    },
                    done: function(e, data) { 
                        // Add a time delay so user will notice upload finishing
                        // for small files
                        setTimeout(
                            function() { renderStaffGrading(data.result); }, 
                            3000)
                    }
                });
            });
        }

        /* Click event handler for "enter grade" */
        function handleGradeEntry() {
            var row = $(this).parents("tr");
            var form = $(element).find("#enter-grade-form");
            $(element).find("#student-name").text(row.data("fullname"));
            form.find("#module_id-input").val(row.data("module_id"));
            form.find("#grade-input").val(row.data("score"));
            form.find("#comment-input").text(row.data("comment"));
            form.off("submit").on("submit", function(event) {
                var max_score = row.parents("#grade-info").data("max_score");
                var score = Number(form.find("#grade-input").val());
                event.preventDefault();
                if (isNaN(score)) {
                    form.find(".error").html("<br/>Grade must be a number.");
                } 
                else if (score < 0) {
                    form.find(".error").html("<br/>Grade must be positive.");
                }
                else if (score > max_score) {
                    form.find(".error").html("<br/>Maximum score is " + max_score);
                }
                else {
                    // No errors
                    $.post(enterGradeUrl, form.serialize())
                        .success(renderStaffGrading);
                }
            });
            form.find("#remove-grade").on("click", function() {
                var url = removeGradeUrl + "?module_id=" + row.data("module_id");
                $.get(url).success(renderStaffGrading);
            });
        }

        $(function($) { // onLoad
            var block = $(element).find(".sga-block");
            var state = block.attr("data-state");
            render(JSON.parse(state));

            var is_staff = block.attr("data-staff") == "True";
            if (is_staff) {
                gradingTemplate = _.template(
                    $(element).find("#sga-grading-tmpl").text());
                block.find("#grade-submissions-button")
                    .leanModal()
                    .on("click", function() {
                        $.ajax({
                            url: getStaffGradingUrl,
                            success: renderStaffGrading
                        });
                    });
            }
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
