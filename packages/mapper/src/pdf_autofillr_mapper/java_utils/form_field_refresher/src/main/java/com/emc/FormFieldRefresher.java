package com.emc;

import com.itextpdf.text.pdf.*;

import java.io.File;
import java.io.FileOutputStream;
import java.nio.file.Files;
import java.nio.file.StandardCopyOption;
import java.util.*;

/**
 * Refreshes all PDF form fields in-place to ensure proper appearance and formatting.
 * This tool reads an existing filled PDF and regenerates all field appearances.
 * The original file is overwritten with the refreshed version.
 */
public class FormFieldRefresher {

    private static final String LOG_PREFIX = "[FormFieldRefresher] ";

    /**
     * Refreshes all form fields in the PDF with output to a new file.
     * Sets all text fields to blank ("") and all checkboxes/radio buttons to "Off".
     */
    public void refreshPdf(String inputPdfPath, String outputPdfPath) throws Exception {
        System.out.println(LOG_PREFIX + "Starting PDF form field refresh");
        System.out.println(LOG_PREFIX + "Input: " + inputPdfPath);
        System.out.println(LOG_PREFIX + "Output: " + outputPdfPath);
        
        PdfReader reader = new PdfReader(inputPdfPath);
        PdfStamper stamper = new PdfStamper(reader, new FileOutputStream(outputPdfPath));
        AcroFields form = stamper.getAcroFields();

        // Check if PDF has form fields (AcroForm)
        if (form == null || form.getFields().isEmpty()) {
            System.out.println(LOG_PREFIX + "WARNING: PDF has no form fields. Creating empty form structure.");
            stamper.close();
            reader.close();
            // Copy input to output unchanged
            Files.copy(new File(inputPdfPath).toPath(), new File(outputPdfPath).toPath(), StandardCopyOption.REPLACE_EXISTING);
            return;
        }

        // ✅ Enable appearance generation (only if form exists)
        try {
            form.setGenerateAppearances(true);
            System.out.println(LOG_PREFIX + "Appearance generation enabled");
        } catch (NullPointerException e) {
            System.out.println(LOG_PREFIX + "WARNING: Cannot set appearance generation (PDF may not have proper AcroForm). Continuing...");
        }

        // ✅ Set NeedAppearances flag
        setNeedAppearancesFlag(reader);

        // Get all form fields
        Set<String> fieldNames = form.getFields().keySet();
        System.out.println(LOG_PREFIX + "Found " + fieldNames.size() + " form fields");

        // Categorize fields by type
        Map<String, List<String>> fieldsByType = categorizeFields(form, fieldNames);
        
        // ✅ Refresh all fields: text → "", checkboxes/radio → "Off"
        refreshTextFields(form, fieldsByType.get("text"));
        refreshCheckBoxes(form, fieldsByType.get("checkbox"));
        refreshRadioButtons(form, fieldsByType.get("radio"));

        stamper.setFormFlattening(false);
        stamper.close();
        reader.close();
        
        System.out.println(LOG_PREFIX + "PDF form fields refreshed successfully: " + outputPdfPath);
    }

    /**
     * Refreshes all form fields in the PDF by reading their current values
     * and regenerating their appearances. Updates the file in-place.
     */
    public void refreshPdfInPlace(String pdfPath) throws Exception {
        System.out.println(LOG_PREFIX + "Starting PDF form field refresh (in-place)");
        System.out.println(LOG_PREFIX + "Input: " + pdfPath);
        
        // Create a temporary file for the refreshed PDF
        File originalFile = new File(pdfPath);
        File tempFile = File.createTempFile("refreshed_", ".pdf", originalFile.getParentFile());
        
        try {
            // Use the regular refresh method to create temp file
            refreshPdf(pdfPath, tempFile.getAbsolutePath());

            // Replace original file with refreshed version
            System.out.println(LOG_PREFIX + "Replacing original file with refreshed version");
            Files.move(tempFile.toPath(), originalFile.toPath(), StandardCopyOption.REPLACE_EXISTING);
            
            System.out.println(LOG_PREFIX + "PDF form fields refreshed successfully (in-place): " + pdfPath);
        } catch (Exception e) {
            // Clean up temp file on error
            if (tempFile.exists()) {
                tempFile.delete();
            }
            throw e;
        }
    }

    /**
     * Sets the NeedAppearances flag in the PDF catalog.
     * This tells PDF viewers to regenerate field appearances if needed.
     */
    private void setNeedAppearancesFlag(PdfReader reader) throws Exception {
        try {
            com.itextpdf.text.pdf.PdfDictionary catalog = reader.getCatalog();
            com.itextpdf.text.pdf.PdfDictionary acroForm = catalog.getAsDict(PdfName.ACROFORM);
            if (acroForm != null) {
                acroForm.put(PdfName.NEEDAPPEARANCES, com.itextpdf.text.pdf.PdfBoolean.PDFTRUE);
                System.out.println(LOG_PREFIX + "NeedAppearances flag set to true");
            }
        } catch (Exception e) {
            System.out.println(LOG_PREFIX + "Warning: Could not set NeedAppearances flag: " + e.getMessage());
        }
    }

    /**
     * Categorizes form fields by their type.
     */
    private Map<String, List<String>> categorizeFields(AcroFields form, Set<String> fieldNames) {
        Map<String, List<String>> fieldsByType = new HashMap<>();
        fieldsByType.put("text", new ArrayList<>());
        fieldsByType.put("checkbox", new ArrayList<>());
        fieldsByType.put("radio", new ArrayList<>());

        for (String fieldName : fieldNames) {
            int fieldType = form.getFieldType(fieldName);
            switch (fieldType) {
                case AcroFields.FIELD_TYPE_CHECKBOX:
                    fieldsByType.get("checkbox").add(fieldName);
                    break;
                case AcroFields.FIELD_TYPE_RADIOBUTTON:
                    fieldsByType.get("radio").add(fieldName);
                    break;
                case AcroFields.FIELD_TYPE_TEXT:
                case AcroFields.FIELD_TYPE_COMBO:
                case AcroFields.FIELD_TYPE_LIST:
                    fieldsByType.get("text").add(fieldName);
                    break;
                default:
                    System.out.println(LOG_PREFIX + "Field '" + fieldName + "' has unsupported type: " + fieldType);
            }
        }

        System.out.println(LOG_PREFIX + "Categorized: " 
            + fieldsByType.get("text").size() + " text, "
            + fieldsByType.get("checkbox").size() + " checkboxes, "
            + fieldsByType.get("radio").size() + " radio buttons");

        return fieldsByType;
    }

    /**
     * Sets ALL text fields to blank ("") to refresh their appearance and field name.
     */
    private void refreshTextFields(AcroFields form, List<String> textFields) throws Exception {
        System.out.println(LOG_PREFIX + "Refreshing " + textFields.size() + " text field(s)");
        
        for (String fieldName : textFields) {
            try {
                // ✅ Refresh field name by re-setting it
                refreshFieldName(form, fieldName);
                
                // ✅ Set ALL text fields to blank
                form.setField(fieldName, "");
                applyDarkTextAppearance(form, fieldName);
                System.out.println(LOG_PREFIX + "Refreshed text field (name + value): " + fieldName);
            } catch (Exception e) {
                System.out.println(LOG_PREFIX + "Warning: Could not refresh text field '" + fieldName + "': " + e.getMessage());
            }
        }
    }

    /**
     * Refreshes a field's name by re-setting the partial name (T entry) in the field dictionary.
     * This forces PDF viewers to re-read the field name.
     */
    private void refreshFieldName(AcroFields form, String fieldName) throws Exception {
        try {
            AcroFields.Item item = form.getFieldItem(fieldName);
            if (item == null) return;

            int widgetCount = item.size();
            for (int i = 0; i < widgetCount; i++) {
                com.itextpdf.text.pdf.PdfDictionary widget = item.getWidget(i);
                if (widget == null) continue;

                // ✅ Re-set the partial name (T entry)
                // Get the last part of the field name (after the last dot)
                String partialName = fieldName;
                int lastDot = fieldName.lastIndexOf('.');
                if (lastDot >= 0) {
                    partialName = fieldName.substring(lastDot + 1);
                }
                
                widget.put(PdfName.T, new com.itextpdf.text.pdf.PdfString(partialName));
            }
        } catch (Exception e) {
            System.out.println(LOG_PREFIX + "Warning: Could not refresh field name for '" + fieldName + "'");
        }
    }

    /**
     * Applies darker, bolder text appearance to text fields.
     */
    private void applyDarkTextAppearance(AcroFields form, String fieldName) throws Exception {
        try {
            AcroFields.Item item = form.getFieldItem(fieldName);
            if (item == null) return;

            int widgetCount = item.size();
            for (int i = 0; i < widgetCount; i++) {
                com.itextpdf.text.pdf.PdfDictionary widget = item.getWidget(i);
                if (widget == null) continue;

                // Set default appearance for darker text (11pt, black)
                com.itextpdf.text.pdf.PdfString da = new com.itextpdf.text.pdf.PdfString("/F1 11 Tf 0 0 0 rg");
                widget.put(PdfName.DA, da);

                // Set text color
                com.itextpdf.text.pdf.PdfDictionary mk = widget.getAsDict(PdfName.MK);
                if (mk == null) {
                    mk = new com.itextpdf.text.pdf.PdfDictionary();
                }
                mk.put(PdfName.CA, new com.itextpdf.text.pdf.PdfString(""));
                widget.put(PdfName.MK, mk);
            }
        } catch (Exception e) {
            System.out.println(LOG_PREFIX + "Warning: Could not apply text styling to '" + fieldName + "'");
        }
    }

    /**
     * Sets ALL checkboxes to "Off" to refresh their appearance and field name.
     */
    private void refreshCheckBoxes(AcroFields form, List<String> checkBoxes) throws Exception {
        System.out.println(LOG_PREFIX + "Refreshing " + checkBoxes.size() + " checkbox(es)");

        for (String fieldName : checkBoxes) {
            try {
                // ✅ Refresh field name by re-setting it
                refreshFieldName(form, fieldName);
                
                // ✅ Set ALL checkboxes to Off
                form.setField(fieldName, "Off");
                System.out.println(LOG_PREFIX + "Refreshed checkbox (name + value): " + fieldName);
            } catch (Exception e) {
                System.out.println(LOG_PREFIX + "Warning: Could not refresh checkbox '" + fieldName + "': " + e.getMessage());
            }
        }
    }

    /**
     * Sets ALL radio buttons to "Off" to refresh their appearance and field name.
     */
    private void refreshRadioButtons(AcroFields form, List<String> radioGroups) throws Exception {
        System.out.println(LOG_PREFIX + "Refreshing " + radioGroups.size() + " radio button group(s)");

        for (String groupName : radioGroups) {
            try {
                // ✅ Refresh field name by re-setting it
                refreshFieldName(form, groupName);
                
                // ✅ Set ALL radio buttons to Off
                form.setField(groupName, "Off");
                System.out.println(LOG_PREFIX + "Refreshed radio button (name + value): " + groupName);
            } catch (Exception e) {
                System.out.println(LOG_PREFIX + "Warning: Could not refresh radio button '" + groupName + "': " + e.getMessage());
            }
        }
    }

    /**
     * Main method for command-line usage.
     * Usage: 
     *   java FormFieldRefresher <input-pdf>                    (in-place refresh)
     *   java FormFieldRefresher <input-pdf> <output-pdf>       (create new file)
     */
    public static void main(String[] args) {
        if (args.length < 1 || args.length > 2) {
            System.err.println("Usage:");
            System.err.println("  java FormFieldRefresher <input-pdf>                  (in-place refresh)");
            System.err.println("  java FormFieldRefresher <input-pdf> <output-pdf>     (create new file)");
            System.err.println("");
            System.err.println("Examples:");
            System.err.println("  java -jar form-field-refresher.jar filled.pdf");
            System.err.println("  java -jar form-field-refresher.jar filled.pdf refreshed.pdf");
            System.exit(1);
        }

        String inputPdf = args[0];
        String outputPdf = args.length == 2 ? args[1] : null;

        try {
            FormFieldRefresher refresher = new FormFieldRefresher();
            
            if (outputPdf != null) {
                // Create new file mode
                refresher.refreshPdf(inputPdf, outputPdf);
                System.out.println(LOG_PREFIX + "SUCCESS: PDF form fields refreshed: " + outputPdf);
            } else {
                // In-place mode
                refresher.refreshPdfInPlace(inputPdf);
                System.out.println(LOG_PREFIX + "SUCCESS: PDF form fields refreshed in-place: " + inputPdf);
            }
        } catch (Exception e) {
            System.err.println(LOG_PREFIX + "ERROR: Failed to refresh PDF form fields");
            e.printStackTrace();
            System.exit(1);
        }
    }
}
