package com.emc;

import com.google.gson.*;
import com.itextpdf.text.Rectangle;
import com.itextpdf.text.pdf.*;

import java.io.FileReader;
import java.io.FileOutputStream;
import java.util.*;

/**
 * Rebuilds PDF form fields by extracting, mapping, and recreating fields with proper appearance preservation.
 */
public class FormFieldRebuilder {

    private static final String LOG_PREFIX = "[FormFieldRebuilder] ";
    private static final float RECT_THRESHOLD = 2.0f;

    // ==================== Data Classes ====================

    public static class FieldMeta {
        public String fid;
        public String matchedKey;
        public String value;
        public int type;
        public int page;
        public Rectangle rect;
        public String groupName;
        public String exportValue;
        public List<String> exportOptions;

        public FieldMeta(String value, int type, int page, Rectangle rect) {
            this.value = value;
            this.type = type;
            this.page = page;
            this.rect = rect;
            this.exportOptions = new ArrayList<>();
        }

        public FieldMeta(String value, int type, int page, Rectangle rect, String groupName, 
                         String exportValue, List<String> exportOptions) {
            this(value, type, page, rect);
            this.groupName = groupName;
            this.exportValue = exportValue;
            this.exportOptions = exportOptions != null ? exportOptions : new ArrayList<>();
        }
    }

    public static class RadioButton {
        private final String fieldName;
        private final String exportValue;

        public RadioButton(String fieldName, String exportValue) {
            this.fieldName = fieldName;
            this.exportValue = exportValue;
        }

        public String getFieldName() { return fieldName; }
        public String getExportValue() { return exportValue; }
    }

    public static class FidMeta {
        public String fid;
        public int page;
        public Rectangle rect;

        public FidMeta(String fid, int page, Rectangle rect) {
            this.fid = fid;
            this.page = page;
            this.rect = rect;
        }
    }

    // ==================== Utility Methods ====================

    /**
     * Compares two rectangles with a threshold for closeness.
     */
    public static boolean rectsAreClose(Rectangle r1, Rectangle r2) {
        return Math.abs(r1.getLeft() - r2.getLeft()) < RECT_THRESHOLD &&
               Math.abs(r1.getRight() - r2.getRight()) < RECT_THRESHOLD &&
               Math.abs(r1.getTop() - r2.getTop()) < RECT_THRESHOLD &&
               Math.abs(r1.getBottom() - r2.getBottom()) < RECT_THRESHOLD;
    }

    /**
     * Loads field metadata from extracted JSON with proper coordinate flipping.
     */
    public static List<FidMeta> loadFidMeta(String jsonPath, PdfReader reader) throws Exception {
        List<FidMeta> result = new ArrayList<>();
        JsonObject obj = JsonParser.parseReader(new FileReader(jsonPath)).getAsJsonObject();
        JsonArray pages = obj.getAsJsonArray("pages");

        System.out.println(LOG_PREFIX + "Loading FID metadata from: " + jsonPath);

        for (JsonElement pageEl : pages) {
            JsonObject pageObj = pageEl.getAsJsonObject();
            int page = pageObj.get("page_number").getAsInt();
            float pageHeight = reader.getPageSize(page).getHeight();

            JsonArray fields = pageObj.getAsJsonArray("form_fields");
            for (JsonElement fieldEl : fields) {
                JsonObject fieldObj = fieldEl.getAsJsonObject();
                String fid = fieldObj.get("fid").getAsString();

                JsonObject bbox = fieldObj.getAsJsonObject("bbox");
                float x0 = bbox.get("left").getAsFloat();
                float y0 = pageHeight - bbox.get("top").getAsFloat();
                float x1 = bbox.get("right").getAsFloat();
                float y1 = pageHeight - bbox.get("bottom").getAsFloat();

                Rectangle rect = new Rectangle(Math.round(x0), Math.round(y0), Math.round(x1), Math.round(y1));
                result.add(new FidMeta(fid, page, rect));
            }
        }

        System.out.println(LOG_PREFIX + "Loaded " + result.size() + " FID metadata entries");
        return result;
    }

    /**
     * Loads FID to key mapping with confidence threshold filtering.
     */
    public static Map<String, String> loadFidToKeyMap(String jsonPath) throws Exception {
        Map<String, String> map = new HashMap<>();
        JsonObject obj = JsonParser.parseReader(new FileReader(jsonPath)).getAsJsonObject();

        System.out.println(LOG_PREFIX + "Loading FID-to-key mapping from: " + jsonPath);

        for (Map.Entry<String, JsonElement> entry : obj.entrySet()) {
            JsonArray arr = entry.getValue().getAsJsonArray();

            if (arr.size() < 3 || arr.get(0).isJsonNull() || arr.get(2).isJsonNull()) {
                continue;
            }

            String matchedKey = arr.get(0).getAsString();
            float confidence = arr.get(2).getAsFloat();

            if (confidence >= 0.7) {
                map.put(entry.getKey(), matchedKey);
            }
        }

        System.out.println(LOG_PREFIX + "Loaded " + map.size() + " FID-to-key mappings (confidence >= 0.7)");
        return map;
    }

    /**
     * Loads radio button field mappings.
     */
    public static Map<String, RadioButton> loadRadioFidToRadioButton(String jsonPath) throws Exception {
        Map<String, RadioButton> fidToRadioButton = new HashMap<>();
        JsonObject obj = JsonParser.parseReader(new FileReader(jsonPath)).getAsJsonObject();

        System.out.println(LOG_PREFIX + "Loading radio button mappings from: " + jsonPath);

        for (Map.Entry<String, JsonElement> groupEntry : obj.entrySet()) {
            JsonObject groupObj = groupEntry.getValue().getAsJsonObject();
            String fieldName = groupObj.get("description").getAsString();
            JsonArray fids = groupObj.getAsJsonArray("radiobutton_fields");
            JsonArray exportValues = groupObj.getAsJsonArray("export_values");

            for (int i = 0; i < fids.size(); i++) {
                String fid = fids.get(i).getAsString();
                String exportValue = (exportValues != null && exportValues.size() > i) 
                    ? exportValues.get(i).getAsString() 
                    : "";
                fidToRadioButton.put(fid, new RadioButton(fieldName, exportValue));
            }
        }

        System.out.println(LOG_PREFIX + "Loaded " + fidToRadioButton.size() + " radio button mappings");
        return fidToRadioButton;
    }

    // ==================== Field Extraction ====================

    /**
     * Extracts metadata from existing PDF form fields.
     */
    public static List<FieldMeta> extractFieldMetadata(String inputPdf) throws Exception {
        List<FieldMeta> fieldMetaList = new ArrayList<>();
        PdfReader reader = new PdfReader(inputPdf);
        AcroFields form = reader.getAcroFields();
        Map<String, AcroFields.Item> fields = form.getFields();

        System.out.println(LOG_PREFIX + "Extracting field metadata from: " + inputPdf);

        for (Map.Entry<String, AcroFields.Item> entry : fields.entrySet()) {
            String fieldName = entry.getKey();
            AcroFields.Item item = entry.getValue();
            int type = form.getFieldType(fieldName);
            int widgetCount = item.size();

            for (int i = 0; i < widgetCount; i++) {
                PdfArray rectArray = item.getWidget(i).getAsArray(PdfName.RECT);
                if (rectArray == null || rectArray.size() != 4) continue;

                float x0 = rectArray.getAsNumber(0).floatValue();
                float y0 = rectArray.getAsNumber(1).floatValue();
                float x1 = rectArray.getAsNumber(2).floatValue();
                float y1 = rectArray.getAsNumber(3).floatValue();
                Rectangle rect = new Rectangle(x0, y1, x1, y0);
                int page = item.getPage(i);

                if (type == AcroFields.FIELD_TYPE_RADIOBUTTON) {
                    PdfDictionary widget = item.getWidget(i);
                    PdfDictionary ap = widget.getAsDict(PdfName.AP);
                    PdfDictionary normal = ap != null ? ap.getAsDict(PdfName.N) : null;
                    List<String> options = new ArrayList<>();

                    if (normal != null) {
                        for (PdfName key : normal.getKeys()) {
                            String opt = key.toString().replaceFirst("/", "");
                            if (!options.contains(opt)) {
                                options.add(opt);
                            }
                        }
                    }

                    PdfDictionary merged = item.getMerged(i);
                    PdfName as = merged.getAsName(PdfName.AS);
                    String exportValue = (as != null) ? as.toString().replaceFirst("/", "") : "";
                    String selectedValue = form.getField(fieldName);
                    fieldMetaList.add(new FieldMeta(selectedValue, type, page, rect, fieldName, exportValue, options));
                } else {
                    String value = form.getField(fieldName);
                    fieldMetaList.add(new FieldMeta(value, type, page, rect));
                }
            }
        }

        System.out.println(LOG_PREFIX + "Extracted " + fieldMetaList.size() + " field metadata entries");
        reader.close();
        return fieldMetaList;
    }

    // ==================== Field Renaming ====================

    /**
     * Renames fields based on FID matching and mapping data.
     */
    public static void renameFields(
        List<FieldMeta> metas,
        List<FidMeta> fids,
        Map<String, String> fidToKeyMap,
        Map<String, RadioButton> fidToRadioButton
    ) {
        System.out.println(LOG_PREFIX + "Renaming " + metas.size() + " fields based on FID matching");

        for (FieldMeta meta : metas) {
            for (FidMeta f : fids) {
                if (f.page == meta.page && rectsAreClose(f.rect, meta.rect)) {
                    if (meta.type == AcroFields.FIELD_TYPE_RADIOBUTTON) {
                        RadioButton rb = fidToRadioButton.get(f.fid);
                        if (rb != null) {
                            meta.groupName = rb.getFieldName();
                            meta.exportValue = rb.getExportValue();
                        } else {
                            meta.groupName = "unmapped_" + f.fid;
                            meta.exportValue = "";
                        }
                    } else {
                        String matchedKey = fidToKeyMap.getOrDefault(f.fid, "unmapped_" + f.fid);
                        meta.groupName = matchedKey;
                    }
                    meta.fid = f.fid;
                    break;
                }
            }

            if (meta.groupName == null) {
                meta.groupName = "unmapped_unknown";
            }
        }
    }

    // ==================== Field Removal ====================

    /**
     * Removes all existing form fields from PDF (clears all field values).
     */
    public static void removeAllFields(String inputPdf, String outputPdf) throws Exception {
        System.out.println(LOG_PREFIX + "Removing all form fields from: " + inputPdf);

        PdfReader reader = new PdfReader(inputPdf);
        PdfStamper stamper = new PdfStamper(reader, new FileOutputStream(outputPdf));
        AcroFields form = stamper.getAcroFields();
        Map<String, AcroFields.Item> fields = form.getFields();

        int fieldCount = 0;
        for (Map.Entry<String, AcroFields.Item> entry : fields.entrySet()) {
            AcroFields.Item item = entry.getValue();
            int widgetCount = item.size();

            for (int i = 0; i < widgetCount; i++) {
                PdfDictionary widget = item.getWidget(i);
                int pageNum = item.getPage(i);
                PdfDictionary pageDict = reader.getPageN(pageNum);
                PdfArray annots = pageDict.getAsArray(PdfName.ANNOTS);

                if (annots != null) {
                    for (int j = 0; j < annots.size(); j++) {
                        PdfObject obj = annots.getPdfObject(j);
                        if (obj != null && obj.equals(widget)) {
                            annots.remove(j);
                            pageDict.put(PdfName.ANNOTS, annots);
                            break;
                        }
                    }
                }

                // Remove all field metadata
                widget.remove(PdfName.T);
                widget.remove(PdfName.V);
                widget.remove(PdfName.FT);
                widget.remove(PdfName.PARENT);
                widget.remove(PdfName.SUBTYPE);
                widget.remove(PdfName.AS);
                widget.remove(PdfName.AP);
                fieldCount++;
            }
        }

        // Clean AcroForm
        PdfDictionary catalog = reader.getCatalog();
        PdfDictionary acroForm = catalog.getAsDict(PdfName.ACROFORM);
        if (acroForm != null) {
            acroForm.remove(PdfName.FIELDS);
            acroForm.remove(PdfName.NEEDAPPEARANCES);
        }

        stamper.close();
        reader.close();
        System.out.println(LOG_PREFIX + "Removed " + fieldCount + " field widgets");
    }

    // ==================== Field Addition ====================

    /**
     * Adds new form fields to PDF.
     */
    public static void addFields(String inputPdf, String outputPdf, List<FieldMeta> fields) throws Exception {
        System.out.println(LOG_PREFIX + "Adding " + fields.size() + " new form fields");

        PdfReader reader = new PdfReader(inputPdf);
        PdfStamper stamper = new PdfStamper(reader, new FileOutputStream(outputPdf));
        PdfWriter writer = stamper.getWriter();

        // Set NeedAppearances for proper rendering
        PdfDictionary catalog = reader.getCatalog();
        PdfDictionary acroForm = catalog.getAsDict(PdfName.ACROFORM);
        if (acroForm != null) {
            acroForm.put(PdfName.NEEDAPPEARANCES, PdfBoolean.PDFTRUE);
        }

        Map<FieldMeta, String> assignedNames = assignFieldNames(fields);
        Map<String, List<FieldMeta>> radioGroups = new LinkedHashMap<>();
        Map<String, List<FieldMeta>> textGroups = new LinkedHashMap<>();
        List<FieldMeta> checkboxes = new ArrayList<>();

        classifyFields(fields, assignedNames, radioGroups, textGroups, checkboxes);

        addRadioGroups(radioGroups, writer, stamper);
        addGroupedTextFields(textGroups, writer, stamper);
        addCheckboxes(checkboxes, assignedNames, writer, stamper);

        stamper.setFormFlattening(false);
        stamper.close();
        reader.close();

        System.out.println(LOG_PREFIX + "Successfully added " + fields.size() + " fields");
    }

    /**
     * Assigns unique field names to metadata objects.
     */
    private static Map<FieldMeta, String> assignFieldNames(List<FieldMeta> fields) {
        Map<FieldMeta, String> nameMap = new HashMap<>();
        for (FieldMeta meta : fields) {
            String key = (meta.groupName != null && !meta.groupName.isEmpty())
                ? meta.groupName
                : "unmapped_" + (meta.fid != null ? meta.fid : UUID.randomUUID().toString());
            nameMap.put(meta, key);
        }
        return nameMap;
    }

    /**
     * Classifies fields by type (radio, text, checkbox).
     */
    private static void classifyFields(List<FieldMeta> fields, Map<FieldMeta, String> assignedNames,
                                       Map<String, List<FieldMeta>> radioGroups,
                                       Map<String, List<FieldMeta>> textGroups,
                                       List<FieldMeta> checkboxes) {
        for (FieldMeta meta : fields) {
            String name = assignedNames.get(meta);
            if (meta.type == AcroFields.FIELD_TYPE_RADIOBUTTON) {
                radioGroups.computeIfAbsent(name, k -> new ArrayList<>()).add(meta);
            } else if (meta.type == AcroFields.FIELD_TYPE_TEXT) {
                textGroups.computeIfAbsent(name, k -> new ArrayList<>()).add(meta);
            } else if (meta.type == AcroFields.FIELD_TYPE_CHECKBOX) {
                checkboxes.add(meta);
            }
        }
    }

    /**
     * Adds radio button groups with proper sizing and appearance.
     */
    /**
 * Adds radio button groups with proper sizing and shape-aware appearances.
 * Supports deselection and auto-detects square vs circular boxes.
 */
/**
 * Adds radio button groups with proper sizing and shape-aware appearances.
 * Supports deselection and auto-detects square vs circular boxes.
 */
private static void addRadioGroups(Map<String, List<FieldMeta>> radioGroups, PdfWriter writer, PdfStamper stamper) throws Exception {
    System.out.println(LOG_PREFIX + "Adding " + radioGroups.size() + " radio button group(s)");
    
    for (Map.Entry<String, List<FieldMeta>> entry : radioGroups.entrySet()) {
        String name = entry.getKey();
        List<FieldMeta> group = entry.getValue();

        // ✅ Create radio group with toggle enabled (allows deselection)
        PdfFormField radioGroup = PdfFormField.createRadioButton(writer, true);
        radioGroup.setFieldName(name);
        radioGroup.put(PdfName.V, PdfName.Off);
        radioGroup.put(PdfName.DV, PdfName.Off);

        for (FieldMeta meta : group) {
            float width = Math.abs(meta.rect.getRight() - meta.rect.getLeft());
            float height = Math.abs(meta.rect.getTop() - meta.rect.getBottom());
            
            // Auto-detect shape
            boolean isSquare = Math.abs(width - height) < 2.0f;
            
            System.out.println(LOG_PREFIX + "  Radio option '" + meta.exportValue + "': " 
                + width + "x" + height + " -> " + (isSquare ? "SQUARE" : "CIRCLE"));
            
            // ✅ CORRECT: Use RadioCheckField but customize appearances after
            RadioCheckField radio = new RadioCheckField(writer, meta.rect, null, meta.exportValue);
            
            // Set the check type based on shape detection
            if (isSquare) {
                radio.setCheckType(RadioCheckField.TYPE_SQUARE);
            } else {
                radio.setCheckType(RadioCheckField.TYPE_CIRCLE);
            }
            
            PdfFormField radioField = radio.getRadioField();
            
            // ✅ Override with custom appearances
            PdfDictionary appearanceDict = new PdfDictionary();
            PdfDictionary normalAppearances = new PdfDictionary();
            
            // "Off" state
            PdfAppearance offApp = createRadioOffAppearance(writer, width, height, isSquare);
            normalAppearances.put(PdfName.Off, offApp.getIndirectReference());
            
            // "On" state with export value
            PdfAppearance onApp = createRadioOnAppearance(writer, width, height, isSquare, meta.exportValue);
            normalAppearances.put(new PdfName(meta.exportValue), onApp.getIndirectReference());
            
            appearanceDict.put(PdfName.N, normalAppearances);
            radioField.put(PdfName.AP, appearanceDict);
            radioField.put(PdfName.AS, PdfName.Off);
            
            radioGroup.addKid(radioField);
        }

        radioGroup.put(PdfName.V, PdfName.Off);
        radioGroup.put(PdfName.AS, PdfName.Off);
        
        stamper.addAnnotation(radioGroup, group.get(0).page);
        System.out.println(LOG_PREFIX + "✓ Radio group '" + name + "' added with " + group.size() + " options (deselectable)");
    }
}

/**
 * Creates "Off" (unselected) appearance - just border, shape-aware.
 */
private static PdfAppearance createRadioOffAppearance(PdfWriter writer, float width, float height, boolean isSquare) {
    PdfAppearance appearance = PdfAppearance.createAppearance(writer, width, height);
    
    appearance.setGrayStroke(0.0f);
    appearance.setLineWidth(1);
    
    if (isSquare) {
        // Square border
        appearance.rectangle(1, 1, width - 2, height - 2);
    } else {
        // Circular border
        float centerX = width / 2;
        float centerY = height / 2;
        float radius = Math.min(width, height) / 2 - 1;
        appearance.circle(centerX, centerY, radius);
    }
    
    appearance.stroke();
    return appearance;
}

/**
 * Creates "On" (selected) appearance - filled shape matching box dimensions.
 */
private static PdfAppearance createRadioOnAppearance(PdfWriter writer, float width, float height, 
                                                     boolean isSquare, String exportValue) {
    PdfAppearance appearance = PdfAppearance.createAppearance(writer, width, height);
    
    // Draw border
    appearance.setGrayStroke(0.0f);
    appearance.setLineWidth(1);
    
    if (isSquare) {
        appearance.rectangle(1, 1, width - 2, height - 2);
    } else {
        float centerX = width / 2;
        float centerY = height / 2;
        float radius = Math.min(width, height) / 2 - 1;
        appearance.circle(centerX, centerY, radius);
    }
    appearance.stroke();
    
    // Fill based on shape with proper sizing
    float padding = Math.min(width, height) * 0.20f;  // 20% padding = 60% fill
    
    appearance.setGrayFill(0.0f);
    
    if (isSquare) {
        // Filled square
        float innerSize = Math.min(width, height) - (2 * padding);
        float offsetX = (width - innerSize) / 2;
        float offsetY = (height - innerSize) / 2;
        appearance.rectangle(offsetX, offsetY, innerSize, innerSize);
        appearance.fill();
    } else {
        // Filled circle
        float centerX = width / 2;
        float centerY = height / 2;
        float innerRadius = (Math.min(width, height) / 2) - padding;
        appearance.circle(centerX, centerY, innerRadius);
        appearance.fill();
    }
    
    return appearance;
}


/**
 * Adds grouped text fields with proper sizing.
 */
private static void addGroupedTextFields(Map<String, List<FieldMeta>> textGroups, PdfWriter writer, PdfStamper stamper) throws Exception {
        for (Map.Entry<String, List<FieldMeta>> entry : textGroups.entrySet()) {
            String name = entry.getKey();
            List<FieldMeta> group = entry.getValue();

            PdfFormField parent = PdfFormField.createTextField(writer, false, false, 100);
            parent.setFieldName(name);

            Set<String> seenLocations = new HashSet<>();

            for (FieldMeta meta : group) {
                String key = meta.page + "|" + meta.rect.toString();

                if (seenLocations.contains(key)) continue;
                seenLocations.add(key);

                TextField tf = new TextField(writer, meta.rect, null);
                tf.setText(meta.value != null ? meta.value : "");
                PdfFormField widget = tf.getTextField();
                widget.setPlaceInPage(meta.page);

                parent.addKid(widget);
            }

            if (!parent.getKids().isEmpty()) {
                int firstPage = group.get(0).page;
                stamper.addAnnotation(parent, firstPage);
                System.out.println(LOG_PREFIX + "Added text group: " + name + " on page " + firstPage);
            }
        }
    }

    /**
     * Adds checkboxes with proper sizing and appearance preservation.
     */
    /**
 * Adds checkboxes with properly scaled tick marks that fit the box dimensions.
 */
/**
 * Adds checkboxes with properly scaled tick marks that fit the box dimensions.
 */
/**
 * Adds checkboxes with TICK MARKS (✓) properly sized to fit boxes.
 */
private static void addCheckboxes(List<FieldMeta> checkboxes, Map<FieldMeta, String> assignedNames, 
                                   PdfWriter writer, PdfStamper stamper) throws Exception {
    System.out.println(LOG_PREFIX + "Adding " + checkboxes.size() + " checkbox(es) with tick marks");
    
    for (FieldMeta meta : checkboxes) {
        String name = assignedNames.getOrDefault(meta, "unmapped_" + meta.fid);
        
        float width = Math.abs(meta.rect.getRight() - meta.rect.getLeft());
        float height = Math.abs(meta.rect.getTop() - meta.rect.getBottom());
        
        // ✅ Use RadioCheckField with TYPE_CHECK for tick marks
        RadioCheckField checkbox = new RadioCheckField(writer, meta.rect, name, "Yes");
        checkbox.setCheckType(RadioCheckField.TYPE_CHECK);  // ✓ TICK MARK (not X)
        checkbox.setBorderWidth(1);
        checkbox.setChecked(false);  // Start unchecked
        
        PdfFormField cb = checkbox.getCheckField();
        cb.setPlaceInPage(meta.page);
        
        stamper.addAnnotation(cb, meta.page);
        
        System.out.println(LOG_PREFIX + "Checkbox (tick) added: " + name + 
            " (" + String.format("%.1fx%.1f", width, height) + ")");
    }
}


/**
 * Creates the "Off" (unchecked) appearance - just a border.
 */
private static PdfAppearance createOffAppearance(PdfWriter writer, float width, float height) {
    PdfAppearance appearance = PdfAppearance.createAppearance(writer, width, height);
    
    // Draw border
    appearance.setGrayStroke(0.0f);
    appearance.setLineWidth(1);
    appearance.rectangle(1, 1, width - 2, height - 2);
    appearance.stroke();
    
    return appearance;
}

/**
 * Creates a scaled checkmark appearance that actually responds to size changes.
 */
private static PdfAppearance createScaledCheckMarkAppearance(PdfWriter writer, float width, float height) {
    PdfAppearance appearance = PdfAppearance.createAppearance(writer, width, height);
    
    System.out.println(LOG_PREFIX + "  Drawing checkmark for box size: " + width + "x" + height);
    
    // Draw border
    appearance.setGrayStroke(0.0f);
    appearance.setLineWidth(1);
    appearance.rectangle(1, 1, width - 2, height - 2);
    appearance.stroke();
    
    // ✅ MINIMAL PADDING: 5% padding = 90% tick mark size
    float padding = Math.min(width, height) * 0.05f;
    float tickWidth = width - (2 * padding);
    float tickHeight = height - (2 * padding);
    
    // ✅ SCALED LINE THICKNESS
    float lineWidth = Math.max(1.8f, Math.min(width, height) * 0.16f);
    
    System.out.println(LOG_PREFIX + "  Tick dimensions: " + tickWidth + "x" + tickHeight + ", line width: " + lineWidth);
    
    // Set drawing properties
    appearance.setGrayStroke(0.0f);
    appearance.setLineWidth(lineWidth);
    appearance.setLineCap(PdfContentByte.LINE_CAP_ROUND);
    appearance.setLineJoin(PdfContentByte.LINE_JOIN_ROUND);
    
    // Checkmark coordinates
    float x1 = padding + (tickWidth * 0.15f);
    float y1 = padding + (tickHeight * 0.45f);
    
    float x2 = padding + (tickWidth * 0.40f);
    float y2 = padding + (tickHeight * 0.10f);
    
    float x3 = padding + (tickWidth * 0.95f);
    float y3 = padding + (tickHeight * 0.90f);
    
    System.out.println(LOG_PREFIX + "  Checkmark path: (" + x1 + "," + y1 + ") -> (" + x2 + "," + y2 + ") -> (" + x3 + "," + y3 + ")");
    
    // Draw the checkmark
    appearance.moveTo(x1, y1);
    appearance.lineTo(x2, y2);
    appearance.lineTo(x3, y3);
    appearance.stroke();
    
    return appearance;
}




    // ==================== Main Rebuild Method ====================

    /**
     * Main method to rebuild form fields end-to-end.
     */
    public static void rebuildForm(String original, String extractedJson, String mappingJson, String radioGroupingJson, String rebuilt) throws Exception {
        String cleaned = original.replace(".pdf", "_cleaned.pdf");

        System.out.println(LOG_PREFIX + "=== Starting Form Rebuild ===");
        System.out.println(LOG_PREFIX + "Input: " + original);

        PdfReader reader = new PdfReader(original);
        List<FidMeta> fidMetaList = loadFidMeta(extractedJson, reader);
        Map<String, String> fidToKeyMap = loadFidToKeyMap(mappingJson);
        List<FieldMeta> fields = extractFieldMetadata(original);
        Map<String, RadioButton> radioFidToRadioButton = loadRadioFidToRadioButton(radioGroupingJson);

        for (FieldMeta meta : fields) {
            if (meta.type == AcroFields.FIELD_TYPE_RADIOBUTTON) {
                RadioButton rb = radioFidToRadioButton.get(meta.fid);
                if (rb != null) {
                    meta.groupName = rb.getFieldName();
                    meta.exportValue = rb.getExportValue();
                }
            }
        }

        reader.close();

        // Clear all field values in extracted metadata
        for (FieldMeta meta : fields) {
            meta.value = "";
        }

        renameFields(fields, fidMetaList, fidToKeyMap, radioFidToRadioButton);
        removeAllFields(original, cleaned);
        addFields(cleaned, rebuilt, fields);

        System.out.println(LOG_PREFIX + "=== Form Rebuild Complete ===");
        System.out.println(LOG_PREFIX + "Output: " + rebuilt);
    }

    // ==================== Main Entry Point ====================

    public static void main(String[] args) throws Exception {
        if (args.length != 5) {
            System.err.println("Usage: java -jar FormFieldRebuilder.jar <original.pdf> <extracted.json> <mapping.json> <radio_button.json> <rebuilt.pdf>");
            System.exit(1);
        }

        try {
            rebuildForm(args[0], args[1], args[2], args[3], args[4]);
            System.out.println("\n✅ SUCCESS: Form rebuild completed successfully");
        } catch (Exception e) {
            System.err.println("\n❌ ERROR: Form rebuild failed");
            e.printStackTrace();
            System.exit(1);
        }
    }
}
