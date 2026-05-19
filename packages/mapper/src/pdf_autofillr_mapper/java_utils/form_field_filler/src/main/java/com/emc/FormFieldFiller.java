package com.emc;

import com.itextpdf.text.pdf.AcroFields;
import com.itextpdf.text.pdf.PdfName;
import com.itextpdf.text.pdf.PdfReader;
import com.itextpdf.text.pdf.PdfStamper;
import com.google.gson.Gson;
import com.google.gson.reflect.TypeToken;

import java.io.FileOutputStream;
import java.io.FileReader;
import java.lang.reflect.Type;
import java.util.*;

/**
 * Fills PDF form fields (text, checkboxes, radio buttons) with data from JSON.
 * Includes text styling (darker, bolder appearance).
 */
public class FormFieldFiller {

    private Map<String, String> inputData;
    private static final String LOG_PREFIX = "[FormFieldFiller] ";

    public FormFieldFiller(String inputJsonPath) throws Exception {
        this.inputData = loadInputData(inputJsonPath);
        System.out.println(LOG_PREFIX + "Loaded input data from: " + inputJsonPath);
    }

    /**
     * Loads JSON data from file into a Map.
     */
    private Map<String, String> loadInputData(String inputJsonPath) throws Exception {
        Gson gson = new Gson();
        Type type = new TypeToken<Map<String, String>>(){}.getType();
        try (FileReader reader = new FileReader(inputJsonPath)) {
            return gson.fromJson(reader, type);
        }
    }

    /**
     * Main method to fill PDF with form data.
     */
    public void fillPdf(String inputPdfPath, String outputPdfPath) throws Exception {
            PdfReader reader = new PdfReader(inputPdfPath);
            PdfStamper stamper = new PdfStamper(reader, new FileOutputStream(outputPdfPath));
            AcroFields form = stamper.getAcroFields();

            // ✅ Disable auto-generation so we can control font size manually
            form.setGenerateAppearances(false);
            System.out.println(LOG_PREFIX + "Appearance generation disabled for manual control");

            // Categorize form fields by type
            Map<String, List<String>> fieldsByType = categorizeFields(form);

            // Fill each field type
            fillTextFields(form, fieldsByType.get("text"));
            fillCheckBoxes(form, fieldsByType.get("checkbox"));
            fillRadioButtons(form, fieldsByType.get("radio"));

            stamper.setFormFlattening(false);
            stamper.close();
            reader.close();

            System.out.println(LOG_PREFIX + "PDF filled successfully: " + outputPdfPath);
        }

    /**
     * Sets the NeedAppearances flag so PDF viewers render fields with proper sizing.
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
     * Categorizes form fields by their type (text, checkbox, radio).
     */
    private Map<String, List<String>> categorizeFields(AcroFields form) {
        Map<String, List<String>> fieldsByType = new HashMap<>();
        fieldsByType.put("text", new ArrayList<>());
        fieldsByType.put("checkbox", new ArrayList<>());
        fieldsByType.put("radio", new ArrayList<>());

        Set<String> fieldNames = form.getFields().keySet();
        System.out.println(LOG_PREFIX + "Found " + fieldNames.size() + " form fields");

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
     * Fills text fields with data from inputData map.
     * For blank/null/false values: sets fixed-size text appearance.
     * Fills with "✓" or "X" for true/yes values.
     * ✅ NEW: Applies darker, bolder text formatting.
     */
    private void fillTextFields(AcroFields form, List<String> textFields) throws Exception {
        System.out.println(LOG_PREFIX + "Filling " + textFields.size() + " text field(s)");
        
        for (String fieldName : textFields) {
            if (!inputData.containsKey(fieldName)) {
                // ✅ Field not in data - set blank with fixed-size appearance
                applyFixedSizeBlankAppearance(form, fieldName);  // Set DA first
                form.setField(fieldName, " ");  // Then set value
                System.out.println(LOG_PREFIX + "Text field '" + fieldName + "' not in input data - set to blank with fixed size");
                continue;
            }
            
            String value = inputData.get(fieldName);
            
            // ✅ For blank/false/no/null values - set blank with fixed-size appearance
            if (value == null || value.trim().isEmpty() || 
                value.equalsIgnoreCase("false") || value.equalsIgnoreCase("no") || 
                value.equalsIgnoreCase("null")) {
                applyFixedSizeBlankAppearance(form, fieldName);  // Set DA first
                form.setField(fieldName, " ");  // Then set value
                System.out.println(LOG_PREFIX + "Text field '" + fieldName + "' has blank/false/no/null value - set to blank with fixed size");
                continue;
            }
            
            // Convert true/yes to tick mark
            String fillValue = value;
            if (value.equalsIgnoreCase("true") || value.equalsIgnoreCase("yes") || 
                value.equalsIgnoreCase("1") || value.equalsIgnoreCase("on")) {
                fillValue = "✓";  // or use "X" if you prefer
                System.out.println(LOG_PREFIX + "Text field '" + fieldName + "' converting true/yes to tick mark");
            }
            
            // ✅ Apply darker/bolder text appearance BEFORE setting field
            try {
                applyDarkTextAppearance(form, fieldName);
                form.setField(fieldName, fillValue);
                System.out.println(LOG_PREFIX + "Text field filled and styled: " + fieldName + " = '" + fillValue + "'");
            } catch (Exception e) {
                form.setField(fieldName, fillValue);
                System.out.println(LOG_PREFIX + "Text field filled (styling skipped): " + fieldName + " = '" + fillValue + "'");
            }
        }
    }

    /**
     * ✅ NEW: Applies fixed-size text appearance to blank fields.
     * This ensures blank fields have consistent, visible styling.
     */
    private void applyFixedSizeBlankAppearance(AcroFields form, String fieldName) {
        try {
            // ✅ Set font size to 11pt using setFieldProperty
            form.setFieldProperty(fieldName, "textsize", 10f, null);
            form.setFieldProperty(fieldName, "textfont", com.itextpdf.text.pdf.BaseFont.createFont(
                com.itextpdf.text.pdf.BaseFont.HELVETICA, 
                com.itextpdf.text.pdf.BaseFont.WINANSI, 
                com.itextpdf.text.pdf.BaseFont.NOT_EMBEDDED), null);
            form.setFieldProperty(fieldName, "textcolor", com.itextpdf.text.BaseColor.BLACK, null);
            
            System.out.println(LOG_PREFIX + "Set font size to 11pt for: " + fieldName);
        } catch (Exception e) {
            System.out.println(LOG_PREFIX + "Warning: Could not apply fixed-size appearance to '" + fieldName + "': " + e.getMessage());
        }
    }

    /**
     * ✅ NEW: Applies darker text appearance to text fields (not bold).
     * Makes text visible and professional-looking.
     */
    private void applyDarkTextAppearance(AcroFields form, String fieldName) throws Exception {
        try {
            // ✅ Set font size to 11pt using setFieldProperty  
            form.setFieldProperty(fieldName, "textsize", 10f, null);
            form.setFieldProperty(fieldName, "textfont", com.itextpdf.text.pdf.BaseFont.createFont(
                com.itextpdf.text.pdf.BaseFont.HELVETICA,  // Regular, not BOLD
                com.itextpdf.text.pdf.BaseFont.WINANSI, 
                com.itextpdf.text.pdf.BaseFont.NOT_EMBEDDED), null);
            form.setFieldProperty(fieldName, "textcolor", com.itextpdf.text.BaseColor.BLACK, null);
        } catch (Exception e) {
            System.out.println(LOG_PREFIX + "Warning: Could not apply text styling to '" + fieldName + "'");
        }
    }

    /**
     * Fills checkboxes with data from inputData map.
     * Preserves original tick appearance and allows unchecking.
     */
    private void fillCheckBoxes(AcroFields form, List<String> checkBoxes) throws Exception {
    System.out.println(LOG_PREFIX + "Processing " + checkBoxes.size() + " checkbox(es)");

    for (String fieldName : checkBoxes) {
        if (!inputData.containsKey(fieldName)) {
            form.setField(fieldName, "Off");
            continue;
        }

        String value = inputData.get(fieldName);
        String[] states = form.getAppearanceStates(fieldName);

        if (states == null || states.length == 0) {
            continue;
        }

        String tickValue = null;
        for (String state : states) {
            if (!state.equalsIgnoreCase("Off")) {
                tickValue = state;
                break;
            }
        }

        if (tickValue == null) {
            continue;
        }

        boolean shouldCheck = value != null && (
                value.equalsIgnoreCase("yes") || 
                value.equalsIgnoreCase("true") ||
                value.equalsIgnoreCase("1") || 
                value.equalsIgnoreCase("on") || 
                value.equalsIgnoreCase(tickValue)
        );

        String fieldValue = shouldCheck ? tickValue : "Off";
        form.setField(fieldName, fieldValue);
        System.out.println(LOG_PREFIX + "Checkbox '" + fieldName + "' set to: " + fieldValue);
    }
}

    /**
     * Fills radio buttons with data from inputData map.
     * Supports unsetting radio buttons by using empty value or "Off".
     */
    private void fillRadioButtons(AcroFields form, List<String> radioGroups) throws Exception {
        System.out.println(LOG_PREFIX + "Processing " + radioGroups.size() + " radio button group(s)");

        for (String groupName : radioGroups) {
            String value = inputData.get(groupName);

            if (value == null || value.isEmpty() || value.equalsIgnoreCase("Off")) {
                form.setField(groupName, "Off");
                System.out.println(LOG_PREFIX + "Radio button '" + groupName + "' unset/cleared");
                continue;
            }

            String[] states = form.getAppearanceStates(groupName);
            if (states != null) {
                System.out.println(LOG_PREFIX + "Radio button '" + groupName + "' states: " + java.util.Arrays.toString(states));
            }

            form.setField(groupName, value);
            System.out.println(LOG_PREFIX + "Radio button '" + groupName + "' set to: " + value);
        }
    }

    /**
     * Main method for command-line usage.
     * Usage: java FormFieldFiller <input-pdf> <input-json> <output-pdf>
     */
    public static void main(String[] args) {
        if (args.length != 3) {
            System.err.println("Usage: java FormFieldFiller <input-pdf> <input-json> <output-pdf>");
            System.exit(1);
        }

        String inputPdf = args[0];
        String inputJson = args[1];
        String outputPdf = args[2];

        try {
            FormFieldFiller filler = new FormFieldFiller(inputJson);
            filler.fillPdf(inputPdf, outputPdf);
            System.out.println(LOG_PREFIX + "SUCCESS: PDF form filled: " + outputPdf);
        } catch (Exception e) {
            System.err.println(LOG_PREFIX + "ERROR: Failed to fill PDF form");
            e.printStackTrace();
            System.exit(1);
        }
    }
}
